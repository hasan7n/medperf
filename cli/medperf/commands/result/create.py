import os
from medperf.commands.execution import Execution
from medperf.entities.result import Result
from medperf.enums import Status
from tabulate import tabulate

from medperf.entities.cube import Cube
from medperf.entities.dataset import Dataset
from medperf.entities.benchmark import Benchmark
from medperf.utils import check_cube_validity
import medperf.config as config
from medperf.exceptions import (
    InvalidArgumentError,
    ExecutionError,
    InvalidEntityError,
    MedperfException,
)


class BenchmarkExecution:
    @classmethod
    def run(
        cls,
        benchmark_uid: int,
        data_uid: str,
        models_uids=None,
        models_input_file=None,
        use_cache=True,
        ignore_errors=False,
        show_summary=False,
        ignore_failed_experiments=False,
    ):
        """Benchmark execution flow.

        Args:
            benchmark_uid (int): UID of the desired benchmark
            data_uid (str): Registered Dataset UID
            models_uids (List|None): list of model UIDs to execute.
                                    if None, model_source will be used
            models_source: can be:
                    str: filename to read from
                    list: list of model uids
                    None: use all benchmark models
        """
        execution = cls(
            benchmark_uid,
            data_uid,
            models_uids,
            models_input_file,
            ignore_errors,
            ignore_failed_experiments,
        )
        execution.prepare()
        execution.validate()
        execution.prepare_models()
        execution.validate_models()
        if use_cache:
            execution.load_cached_results()
        with execution.ui.interactive():
            results = execution.run_experiments()
        if show_summary:
            execution.print_summary()
        return results

    def __init__(
        self,
        benchmark_uid: int,
        data_uid: int,
        models_uids: int,
        models_input_file: str = None,
        ignore_errors=False,
        ignore_failed_experiments=False,
    ):
        self.benchmark_uid = benchmark_uid
        self.data_uid = data_uid
        self.models_uids = models_uids
        self.models_input_file = models_input_file
        self.ui = config.ui
        self.evaluator = None
        self.ignore_errors = ignore_errors
        self.ignore_failed_experiments = ignore_failed_experiments
        self.cached_results = {}
        self.experiments = []

    def prepare(self):
        self.benchmark = Benchmark.get(self.benchmark_uid)
        self.ui.print(f"Benchmark Execution: {self.benchmark.name}")
        self.dataset = Dataset.get(self.data_uid)
        evaluator_uid = self.benchmark.evaluator
        self.evaluator = self.__get_cube(evaluator_uid, "Evaluator")

    def validate(self):
        dset_prep_cube = str(self.dataset.preparation_cube_uid)
        bmark_prep_cube = str(self.benchmark.data_preparation)

        if self.dataset.uid is None:
            msg = "The provided dataset is not registered."
            raise InvalidArgumentError(msg)

        if dset_prep_cube != bmark_prep_cube:
            msg = "The provided dataset is not compatible with the specified benchmark."
            raise InvalidArgumentError(msg)

    def prepare_models(self):
        if self.models_input_file:
            self.models_uids = self.__get_models_from_file()
        elif self.models_uids is None:
            self.models_uids = self.benchmark.models

    def __get_models_from_file(self):
        if not os.path.exists(self.models_input_file):
            raise InvalidArgumentError("The given file does not exist")
        with open(self.models_input_file) as f:
            text = f.read()
        models = text.strip().split(",")
        try:
            return list(map(int, models))
        except ValueError as e:
            msg = f"Could not parse the given file: {e}. "
            msg += "The file should contain a list of comma-separated integers"
            raise InvalidArgumentError(msg)

    def validate_models(self):
        in_assoc_cubes = set(self.models_uids).issubset(set(self.benchmark.models))
        if not in_assoc_cubes:
            msg = "Some of the provided models is not part of the specified benchmark."
            raise InvalidArgumentError(msg)

    def load_cached_results(self):
        results = Result.all()
        benchmark_dset_results = [
            result
            for result in results
            if result.benchmark_uid == self.benchmark_uid
            and result.dataset_uid == self.data_uid
        ]
        self.cached_results = {
            result.model_uid: result for result in benchmark_dset_results
        }

    def __get_cube(self, uid: int, name: str) -> Cube:
        self.ui.text = f"Retrieving {name} cube"
        cube = Cube.get(uid)
        self.ui.print(f"> {name} cube download complete")
        check_cube_validity(cube)
        return cube

    def run_experiments(self):
        for model_uid in self.models_uids:
            if model_uid in self.cached_results:
                self.experiments.append(
                    {
                        "model_uid": str(model_uid),
                        "result": self.cached_results[model_uid],
                        "cached": True,
                        "error": "",
                    }
                )
                continue

            try:
                model_cube = self.__get_cube(model_uid, "Model")
                execution_summary = Execution.run(
                    dataset=self.dataset,
                    model=model_cube,
                    evaluator=self.evaluator,
                    ignore_errors=self.ignore_errors,
                )
            except MedperfException as e:
                self.__handle_experiment_error(model_uid, e)
                self.experiments.append(
                    {
                        "model_uid": str(model_uid),
                        "result": None,
                        "cached": False,
                        "error": str(e),
                    }
                )
                continue

            partial = execution_summary["partial"]
            results = execution_summary["results"]
            result = self.__write_result(model_uid, results, partial)

            self.experiments.append(
                {
                    "model_uid": str(model_uid),
                    "result": result,
                    "cached": False,
                    "error": "",
                }
            )
        return [experiment["result"] for experiment in self.experiments]

    def __handle_experiment_error(self, model_uid, exception):
        if isinstance(exception, InvalidEntityError):
            config.ui.print_error(
                f"There was an error when retrieving the model mlcube {model_uid}: {exception}"
            )
        elif isinstance(exception, ExecutionError):
            config.ui.print_error(
                f"There was an error when executing the benchmark with the model {model_uid}: {exception}"
            )
        else:
            raise exception
        if not self.ignore_failed_experiments:
            raise exception

    def __result_dict(self, model_uid, results, partial):
        return {
            "id": None,
            "name": f"b{self.benchmark_uid}m{model_uid}d{self.data_uid}",
            "owner": None,
            "benchmark": self.benchmark_uid,
            "model": model_uid,
            "dataset": self.data_uid,
            "results": results,
            "metadata": {"partial": partial},
            "approval_status": Status.PENDING.value,
            "approved_at": None,
            "created_at": None,
            "modified_at": None,
        }

    def __write_result(self, model_uid, results, partial):
        results_info = self.__result_dict(model_uid, results, partial)
        result = Result(results_info)
        result.write()
        return result

    def print_summary(self):
        headers = ["model", "result_uid", "partial", "from cache" "error"]
        data_lists_for_display = []

        num_total = len(self.experiments)
        num_success_run = 0
        num_failed = 0
        num_skipped = 0
        num_partial_skipped = 0
        num_partial_run = 0
        for experiment in self.experiments:
            # populate display data
            if experiment["result"]:
                data_lists_for_display.append(
                    [
                        experiment["model_uid"],
                        experiment["result"].generated_uid,
                        experiment["result"].metadata["partial"],
                        experiment["cached"],
                        experiment["error"],
                    ]
                )
            else:
                data_lists_for_display.append(
                    [experiment["model_uid"], "", "", "", experiment["error"]]
                )

            # statistics
            if experiment["error"]:
                num_failed += 1
            elif experiment["cached"]:
                num_skipped += 1
                if experiment["result"].metadata["partial"]:
                    num_partial_skipped += 1
            elif experiment["result"]:
                num_success_run += 1
                if experiment["result"].metadata["partial"]:
                    num_partial_run += 1

        tab = tabulate(data_lists_for_display, headers=headers)

        msg = f"Total number of models: {num_total}\n"
        msg += f"\t{num_skipped} were skipped (already executed), "
        msg += f"of which {num_partial_run} have partial results\n"
        msg += f"\t{num_failed} failed\n"
        msg += f"\t{num_success_run} ran successfully, "
        msg += f"of which {num_partial_run} have partial results\n"

        config.ui.print(tab)
        config.ui.print(msg)
