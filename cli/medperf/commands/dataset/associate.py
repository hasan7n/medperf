from medperf import config
from medperf.entities.dataset import Dataset
from medperf.entities.benchmark import Benchmark
from medperf.utils import dict_pretty_print, approval_prompt
from medperf.commands.compatibility_test import CompatibilityTestExecution
from medperf.exceptions import CleanExit, InvalidArgumentError


class AssociateDataset:
    @staticmethod
    def run(data_uid: str, benchmark_uid: int, approved=False, force_test=False):
        """Associates a registered dataset with a benchmark

        Args:
            data_uid (int): UID of the registered dataset to associate
            benchmark_uid (int): UID of the benchmark to associate with
        """
        comms = config.comms
        ui = config.ui
        dset = Dataset.get(data_uid)
        if dset.id is None:
            msg = "The provided dataset is not registered."
            raise InvalidArgumentError(msg)

        benchmark = Benchmark.get(benchmark_uid)

        if str(dset.data_preparation_mlcube) != str(benchmark.data_preparation_mlcube):
            raise InvalidArgumentError(
                "The specified dataset wasn't prepared for this benchmark"
            )

        _, _, _, result = CompatibilityTestExecution.run(
            benchmark_uid, data_uid=data_uid, force_test=force_test
        )
        ui.print("These are the results generated by the compatibility test. ")
        ui.print("This will be sent along the association request.")
        ui.print("They will not be part of the benchmark.")
        dict_pretty_print(result.results)

        msg = "Please confirm that you would like to associate"
        msg += f" the dataset {dset.name} with the benchmark {benchmark.name}."
        msg += " [Y/n]"
        approved = approved or approval_prompt(msg)
        if approved:
            ui.print("Generating dataset benchmark association")
            metadata = {"test_result": result.results}
            comms.associate_dset(dset.id, benchmark_uid, metadata)
        else:
            raise CleanExit("Dataset association operation cancelled.")
