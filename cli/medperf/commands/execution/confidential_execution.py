import logging
import os
from time import time

import yaml

from medperf.commands.execution.plan import BenchmarkPlan
from medperf.entities.model import Model
from medperf.entities.dataset import Dataset
from medperf.entities.execution import Execution
import medperf.config as config
from medperf.exceptions import DecryptionError, ExecutionError, CommunicationError

from medperf.account_management import get_medperf_user_object
from medperf.cc.config import runner_for
from medperf.cc.operator import (
    download_results,
    run_workload,
    wait_for_workload,
    workload_configs,
    workload_results_exists,
)
from medperf.cc.parties import check_operator_is_allowed, collector_public_key
from medperf.utils import get_string_hash
from medperf.commands.certificate.utils import load_user_private_key
from medperf.containers.runners.docker_utils import full_docker_image_name
from medperf.enums import CryptoKeyType
from medperf_cc import WorkloadIdentity
from medperf_cc.proof import IntegrityProof


class ConfidentialExecution:
    """Runs an `end_to_end_script` benchmark inside a confidential VM.

    The benchmark script loads the model asset, runs inference and computes the
    metrics in one step, so nothing but the encrypted results leaves the VM."""

    @classmethod
    def run(
        cls,
        plan: BenchmarkPlan,
        dataset: Dataset,
        model: Model,
        execution: Execution = None,
        ignore_model_errors=False,
    ):
        """Benchmark execution flow.

        Args:
            plan (BenchmarkPlan): the benchmark's resolved components
            dataset (Dataset): Registered Dataset
            model (Model): the asset model to execute
        """
        execution_flow = cls(plan, dataset, model, execution, ignore_model_errors)
        execution_flow.get_operator()
        execution_flow.validate()
        execution_flow.prepare()
        execution_flow.set_pending_status()
        execution_flow.setup_workload()
        execution_flow.run_workload()
        execution_flow.wait_for_workload_completion()
        execution_flow.download_results()
        execution_summary = execution_flow.todict()
        return execution_summary

    def __init__(
        self,
        plan: BenchmarkPlan,
        dataset: Dataset,
        model: Model,
        execution: Execution = None,
        ignore_model_errors=False,
    ):
        self.comms = config.comms
        self.ui = config.ui
        self.plan = plan
        self.benchmark_id = plan.benchmark_id
        self.dataset = dataset
        self.model = model
        self.script = plan.script
        self.execution = execution
        self.ignore_model_errors = ignore_model_errors
        self.operator = None
        self.runner = None
        self.integrity_proof = None
        self.dataset_cc_config = None
        self.model_cc_config = None

    def get_operator(self):
        self.operator = get_medperf_user_object()

    def validate(self):
        if not self.dataset.is_cc_configured():
            raise ExecutionError(
                f"Dataset {self.dataset.id} is not configured for confidential computing."
            )
        if not self.model.is_cc_configured():
            raise ExecutionError(
                f"Model {self.model.id} is not configured for confidential computing."
            )
        if not self.operator.is_cc_configured():
            raise ExecutionError(
                "User does not have a configuration to operate a confidential execution."
            )
        check_operator_is_allowed(
            self.operator.id, self.benchmark_id, self.dataset, self.model
        )

    def prepare(self):
        self.dataset_cc_config, self.model_cc_config = workload_configs(
            self.dataset, self.model
        )
        self.runner = runner_for(self.operator)
        self.asset = self.model.asset_obj

    def set_pending_status(self):
        self.__send_report("pending")

    def setup_workload(self):
        result_collector_public_key = collector_public_key()
        workload = WorkloadIdentity(
            data_hash=self.dataset.generated_uid,
            model_hash=self.asset.asset_hash,
            script_hash=self.plan.script_hash,
            result_collector_hash=get_string_hash(result_collector_public_key),
            data_id=self.dataset.id,
            model_id=self.model.id,
            script_id=self.plan.script_id,
        )

        self.workload = workload
        self.result_collector_public_key = result_collector_public_key

    def run_workload(self):
        config.ui.text = "Running CC workload..."
        docker_image = self.script.parser.get_setup_args()
        docker_image = full_docker_image_name(docker_image)
        run_workload(
            self.runner,
            docker_image,
            self.workload,
            self.dataset_cc_config,
            self.model_cc_config,
            self.result_collector_public_key.decode("utf-8"),
        )

    def wait_for_workload_completion(self):
        config.ui.text = "Waiting for workload completion"
        wait_for_workload(self.runner, self.workload)
        if not workload_results_exists(self.runner, self.workload):
            raise ExecutionError("Workload did not complete successfully.")

    def download_results(self):
        config.ui.text = "Downloading results..."
        timestamp = str(time()).replace(".", "_")
        results_path = os.path.join(
            config.script_result_folder, str(self.execution.id), timestamp
        )
        private_key_bytes = load_user_private_key(CryptoKeyType.RSA)
        if private_key_bytes is None:
            raise DecryptionError("Missing Private Key")

        download_results(
            self.runner, self.workload, private_key_bytes, results_path
        )

        results_dir = os.path.join(results_path, "results")
        results_file = os.path.join(results_dir, "results.yaml")
        if os.path.exists(results_file):
            with open(results_file, "r") as f:
                results_content = yaml.safe_load(f)
            self.results = results_content
        else:
            self.results = {}

        self.integrity_proof = IntegrityProof.from_results_dir(results_dir)
        if self.integrity_proof is None:
            logging.warning(
                "The workload produced no integrity proof;"
                " these results cannot be verified."
            )

    def todict(self):
        return {
            "results": self.results,
            "partial": False,
            "integrity_proof": (
                self.integrity_proof.todict() if self.integrity_proof else {}
            ),
        }

    def __send_report(self, status: str):
        if self.execution is None or self.execution.id is None:
            return

        execution_id = self.execution.id
        body = {"script_report": {"execution_status": status}}
        try:
            config.comms.update_execution(execution_id, body)
        except CommunicationError as e:
            logging.error(str(e))
            return
