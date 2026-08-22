from medperf.commands.execution.plan import BenchmarkPlan
from medperf.entities.benchmark import Benchmark
from medperf.entities.model import Model
from medperf.entities.dataset import Dataset
from medperf.entities.execution import Execution
import medperf.config as config
from medperf.exceptions import ExecutionError

from medperf.account_management import get_medperf_user_object
from medperf.cc.collector import resolve_collector
from medperf.cc.config import result_store_for, runner_for
from medperf.cc.operator import (
    run_workload,
    workload_configs,
    wait_for_workload,
)
from medperf.cc.results import fetch_results, results_exist
from medperf.utils import get_string_hash
from medperf.commands.execution.container_execution import ContainerExecution
from medperf_cc import WorkloadIdentity


class ConfidentialModelContainerExecution:
    """Runs an `inference_script` benchmark's inference step in a confidential VM.

    The benchmark script loads the model asset and produces predictions inside
    the VM; the predictions come back encrypted and are then scored locally by
    the benchmark's evaluator."""

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
        execution_flow.setup_local_environment()
        with config.ui.interactive():
            execution_flow.get_operator()
            execution_flow.validate()
            execution_flow.prepare()
            execution_flow.setup_workload()
            if not execution_flow.results_exist():
                execution_flow.run_workload()
                execution_flow.wait_for_workload_completion()
            execution_flow.download_predictions()
            execution_flow.run_evaluation()
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
        self.evaluator = plan.evaluator
        self.execution = execution
        self.ignore_model_errors = ignore_model_errors
        self.operator = None
        self.runner = None
        self.collector = None
        self.result_store = None
        self.dataset_cc_config = None
        self.model_cc_config = None
        self.local_execution_flow = None

    def setup_local_environment(self):
        self.local_execution_flow = ContainerExecution(
            self.dataset,
            self.model,
            self.evaluator,
            self.execution,
            self.ignore_model_errors,
        )
        self.local_execution_flow.prepare()

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
        if self.dataset.owner != self.operator.id:
            raise ExecutionError(
                "An inference_script benchmark scores the predictions on-prem,"
                " against ground truth labels only the data owner holds."
                " This execution must be operated by the data owner."
            )

    def prepare(self):
        self.dataset_cc_config, self.model_cc_config = workload_configs(
            self.dataset, self.model
        )
        # An inference_script run is always collected by the data owner, who
        # validate() has just required to be the operator. Resolving still
        # runs, to refuse a pair of policies that would release the
        # predictions to somebody else, or to nobody.
        self.collector = resolve_collector(
            Benchmark.get(self.benchmark_id), self.dataset, self.model
        )
        if self.collector.user_id != self.operator.id:
            raise ExecutionError(
                "An inference_script benchmark scores the predictions on-prem,"
                " but its policies release them to the"
                f" {self.collector.party.value}. Only the data owner can"
                " collect an execution they have to score themselves."
            )
        self.runner = runner_for(self.operator)
        self.result_store = result_store_for(self.collector.settings)
        self.asset = self.model.asset_obj

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

    def results_exist(self):
        return results_exist(self.result_store, self.workload)

    def run_workload(self):
        config.ui.text = "Starting Confidential VM"
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
        if not self.results_exist():
            raise ExecutionError("Workload did not complete successfully.")

    def download_predictions(self):
        config.ui.text = "Downloading inference predictions"
        fetch_results(
            self.result_store, self.workload, self.local_execution_flow.preds_path
        )

    def run_evaluation(self):
        return self.local_execution_flow.run_evaluation()

    def todict(self):
        return self.local_execution_flow.todict()
