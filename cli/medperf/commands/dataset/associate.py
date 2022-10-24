from medperf import config
from medperf.entities.dataset import Dataset
from medperf.entities.benchmark import Benchmark
from medperf.utils import dict_pretty_print, pretty_error, approval_prompt
from medperf.commands.compatibility_test import CompatibilityTestExecution


class AssociateDataset:
    @staticmethod
    def run(data_uid: str, benchmark_uid: int, approved=False):
        """Associates a registered dataset with a benchmark

        Args:
            data_uid (int): UID of the registered dataset to associate
            benchmark_uid (int): UID of the benchmark to associate with
        """
        comms = config.comms
        ui = config.ui
        dset = Dataset.from_generated_uid(data_uid)
        if dset.uid is None:
            msg = "The provided dataset is not registered."
            pretty_error(msg)

        benchmark = Benchmark.get(benchmark_uid)

        if str(dset.preparation_cube_uid) != str(benchmark.data_preparation):
            pretty_error("The specified dataset wasn't prepared for this benchmark")

        _, _, _, result = CompatibilityTestExecution.run(
            benchmark_uid, data_uid=data_uid
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
            comms.associate_dset(dset.uid, benchmark_uid, metadata)
        else:
            pretty_error(
                "Dataset association operation cancelled", add_instructions=False
            )
