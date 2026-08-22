import logging

from medperf.commands.execution.plan import BenchmarkPlan
from medperf.entities.benchmark import Benchmark
from medperf.entities.model import Model
from medperf.entities.dataset import Dataset
from medperf.entities.execution import Execution
import medperf.config as config
from medperf.exceptions import ExecutionError, CommunicationError

from medperf.account_management import get_medperf_user_object
from medperf.cc.collector import resolve_collector
from medperf.cc.config import result_store_for, runner_for
from medperf.cc.operator import (
    run_workload,
    wait_for_workload,
    workload_configs,
)
from medperf.cc.results import download_results, results_exist
from medperf.utils import get_string_hash
from medperf_cc import WorkloadIdentity


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
        execution: Execution,
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
        execution_flow.record_collector()
        execution_flow.set_pending_status()
        execution_flow.setup_workload()
        execution_flow.run_workload()
        execution_flow.wait_for_workload_completion()
        execution_flow.collect_results()
        execution_summary = execution_flow.todict()
        return execution_summary

    def __init__(
        self,
        plan: BenchmarkPlan,
        dataset: Dataset,
        model: Model,
        execution: Execution,
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
        self.collector = None
        self.result_store = None
        # Stays empty when the results are somebody else's to collect.
        self.results = {}
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
        if not self.operator.cc_operator.configured:
            raise ExecutionError(
                "User does not have a configuration to operate a confidential execution."
            )

    def prepare(self):
        self.dataset_cc_config, self.model_cc_config = workload_configs(
            self.dataset, self.model
        )
        # Who the results are for. Not a check on the operator: anybody may
        # run the machine, and this refuses only when the asset owners have
        # not agreed on a single party to release the results to.
        self.collector = resolve_collector(
            Benchmark.get(self.benchmark_id), self.dataset, self.model
        )
        self.runner = runner_for(self.operator)
        self.result_store = result_store_for(self.collector.settings)
        self.asset = self.model.asset_obj

    def record_collector(self):
        """Tells the server who these results will be for.

        The operator can do this and the collector cannot: the execution is
        the operator's until it exists. Recording it is what later lets the
        collector read and report an execution they did not create, and it is
        write-once, so it cannot be pointed at somebody else afterwards."""
        if self.collecting_for_operator:
            return
        try:
            config.comms.update_execution(
                self.execution.id, {"result_collector": self.collector.user_id}
            )
        except CommunicationError as e:
            raise ExecutionError(
                "Could not record who the results of this execution are for,"
                f" so the {self.collector.party.value} would not be able to"
                f" collect them: {e}"
            )

    @property
    def collecting_for_operator(self) -> bool:
        return self.collector.user_id == self.operator.id

    def set_pending_status(self):
        self.__send_report("pending")

    def setup_workload(self):
        result_collector_public_key = self.collector.public_key
        workload = WorkloadIdentity(
            data_hash=self.dataset.generated_uid,
            model_hash=self.asset.asset_hash,
            script_hash=self.plan.script_hash,
            result_collector_hash=get_string_hash(result_collector_public_key),
            data_id=self.dataset.id,
            model_id=self.model.id,
            script_id=self.plan.script_id,
            execution_id=self.execution.id,
        )

        self.workload = workload
        self.result_collector_public_key = result_collector_public_key

    def run_workload(self):
        config.ui.text = "Running CC workload..."
        docker_image = self.script.full_docker_image_name
        run_workload(
            self.runner,
            docker_image,
            self.workload,
            self.dataset_cc_config,
            self.model_cc_config,
            self.result_store.receiver_config(self.workload),
            self.result_collector_public_key.decode("utf-8"),
        )

    def wait_for_workload_completion(self):
        config.ui.text = "Waiting for workload completion"
        wait_for_workload(self.runner, self.workload)

    def collect_results(self):
        """Picks the results up, when they are this user's to pick up.

        They land in the collector's own storage, encrypted for the collector's
        key. An operator who is somebody else can neither reach them nor open
        them, and says so rather than reporting an execution that produced
        nothing -- the collector fetches them with `download_cc_results`."""
        if not self.collecting_for_operator:
            config.ui.print_warning(
                f"Results were written for the {self.collector.party.value},"
                " who is not you. They are encrypted for their key, so only"
                " they can fetch them: `medperf confidential"
                f" download_cc_results -e {self.execution.id}`."
            )
            return

        if not results_exist(self.result_store, self.workload):
            raise ExecutionError("Workload did not complete successfully.")
        self.results, self.integrity_proof = download_results(
            self.result_store, self.workload, self.execution.id
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
        execution_id = self.execution.id
        body = {"script_report": {"execution_status": status}}
        try:
            config.comms.update_execution(execution_id, body)
        except CommunicationError as e:
            logging.error(str(e))
            return
