import logging
from typing import List

from medperf.commands.execution import Execution
from medperf.entities.dataset import Dataset
from medperf.entities.benchmark import Benchmark
from medperf.entities.report import TestReport
from medperf.exceptions import InvalidArgumentError
from .validate_params import CompatibilityTestParamsValidator
from .utils import download_demo_data, prepare_cube, get_cube, create_test_dataset


class CompatibilityTestExecution:
    @classmethod
    def run(
        cls,
        benchmark: int = None,
        data_prep: str = None,
        model: str = None,
        evaluator: str = None,
        data_path: str = None,
        labels_path: str = None,
        demo_dataset_url: str = None,
        demo_dataset_hash: str = None,
        data_uid: str = None,
        no_cache: bool = False,
        offline: bool = False,
        skip_data_preparation_step: bool = False,
    ) -> List:
        """Execute a test workflow. Components of a complete workflow should be passed.
        When only the benchmark is provided, it implies the following workflow will be used:
        - the benchmark's demo dataset is used as the raw data
        - the benchmark's data preparation cube is used
        - the benchmark's reference model cube is used
        - the benchmark's metrics cube is used

        Overriding benchmark's components:
        - The data prepration, model, and metrics cubes can be overriden by specifying a cube either
        as an integer (registered) or a path (local). The path can refer either to the mlcube config
        file or to the mlcube directory containing the mlcube config file.
        - Instead of using the demo dataset of the benchmark, The input raw data can be overriden by providing:
            - a demo dataset url and its hash
            - data path and labels path
        - A prepared dataset can be directly used. In this case the data preparator cube is never used.
        The prepared data can be provided by either specifying an integer (registered) or a hash of a
        locally prepared dataset.

        Whether the benchmark is provided or not, the command will fail either if the user fails to
        provide a valid complete workflow, or if the user provided extra redundant parameters.


        Args:
            benchmark (int, optional): Benchmark to run the test workflow for
            data_prep (str, optional): data preparation mlcube uid or local path.
            model (str, optional): model mlcube uid or local path.
            evaluator (str, optional): evaluator mlcube uid or local path.
            data_path (str, optional): path to a local raw data
            labels_path (str, optional): path to the labels of the local raw data
            demo_dataset_url (str, optional): Identifier to download the demonstration dataset tarball file.\n
            See `medperf mlcube submit --help` for more information
            demo_dataset_hash (str, optional): The hash of the demo dataset tarball file
            data_uid (str, optional): A prepared dataset UID
            no_cache (bool): Whether to ignore cached results of the test execution. Defaults to False.
            offline (bool): Whether to disable communication to the MedPerf server and rely only on
            local copies of the server assets. Defaults to False.

        Returns:
            (str): Prepared Dataset UID used for the test. Could be the one provided or a generated one.
            (dict): Results generated by the test.
        """
        logging.info("Starting test execution")
        test_exec = cls(
            benchmark,
            data_prep,
            model,
            evaluator,
            data_path,
            labels_path,
            demo_dataset_url,
            demo_dataset_hash,
            data_uid,
            no_cache,
            offline,
            skip_data_preparation_step,
        )
        test_exec.validate()
        test_exec.set_data_source()
        test_exec.process_benchmark()
        test_exec.prepare_cubes()
        test_exec.prepare_dataset()
        test_exec.initialize_report()
        results = test_exec.cached_results()
        if results is None:
            results = test_exec.execute()
            test_exec.write(results)
        return test_exec.data_uid, results

    def __init__(
        self,
        benchmark: int = None,
        data_prep: str = None,
        model: str = None,
        evaluator: str = None,
        data_path: str = None,
        labels_path: str = None,
        demo_dataset_url: str = None,
        demo_dataset_hash: str = None,
        data_uid: str = None,
        no_cache: bool = False,
        offline: bool = False,
        skip_data_preparation_step: bool = False,
    ):
        self.benchmark_uid = benchmark
        self.data_prep = data_prep
        self.model = model
        self.evaluator = evaluator
        self.data_path = data_path
        self.labels_path = labels_path
        self.demo_dataset_url = demo_dataset_url
        self.demo_dataset_hash = demo_dataset_hash
        self.data_uid = data_uid
        self.no_cache = no_cache
        self.offline = offline
        self.skip_data_preparation_step = skip_data_preparation_step

        # This property will be set to either "path", "demo", "prepared", or "benchmark"
        self.data_source = None

        self.dataset = None
        self.model_cube = None
        self.evaluator_cube = None

        self.validator = CompatibilityTestParamsValidator(
            self.benchmark_uid,
            self.data_prep,
            self.model,
            self.evaluator,
            self.data_path,
            self.labels_path,
            self.demo_dataset_url,
            self.demo_dataset_hash,
            self.data_uid,
        )

    def validate(self):
        self.validator.validate()

    def set_data_source(self):
        self.data_source = self.validator.get_data_source()

    def process_benchmark(self):
        """Process the benchmark input if given. Sets the needed parameters from
        the benchmark."""
        if not self.benchmark_uid:
            return

        benchmark = Benchmark.get(self.benchmark_uid, local_only=self.offline)
        if self.data_source != "prepared":
            self.data_prep = self.data_prep or benchmark.data_preparation_mlcube
        self.model = self.model or benchmark.reference_model_mlcube
        self.evaluator = self.evaluator or benchmark.data_evaluator_mlcube
        if self.data_source == "benchmark":
            self.demo_dataset_url = benchmark.demo_dataset_tarball_url
            self.demo_dataset_hash = benchmark.demo_dataset_tarball_hash
            self.skip_data_preparation_step = benchmark.metadata.get(
                "demo_dataset_already_prepared", False
            )

    def prepare_cubes(self):
        """Prepares the mlcubes. If the provided mlcube is a path, it will create
        a temporary uid and link the cube path to the medperf storage path."""

        if self.data_source != "prepared":
            logging.info(f"Establishing the data preparation cube: {self.data_prep}")
            self.data_prep = prepare_cube(self.data_prep)

        logging.info(f"Establishing the model cube: {self.model}")
        self.model = prepare_cube(self.model)
        logging.info(f"Establishing the evaluator cube: {self.evaluator}")
        self.evaluator = prepare_cube(self.evaluator)

        self.model_cube = get_cube(self.model, "Model", local_only=self.offline)
        self.evaluator_cube = get_cube(
            self.evaluator, "Evaluator", local_only=self.offline
        )

    def prepare_dataset(self):
        """Assigns the data_uid used for testing and retrieves the dataset.
        If the data is not prepared, it calls the data preparation step
        on the given local data path or using a remote demo dataset."""

        logging.info("Establishing data_uid for test execution")
        if self.data_source != "prepared":
            if self.data_source == "path":
                data_path, labels_path = self.data_path, self.labels_path
                # TODO: this has to be redesigned. Compatibility tests command
                #       is starting to have a lot of input arguments. For now
                #       let's not support accepting a metadata path
                metadata_path = None
            else:
                data_path, labels_path, metadata_path = download_demo_data(
                    self.demo_dataset_url, self.demo_dataset_hash
                )

            self.data_uid = create_test_dataset(
                data_path,
                labels_path,
                metadata_path,
                self.data_prep,
                self.skip_data_preparation_step,
            )

        self.dataset = Dataset.get(self.data_uid, local_only=self.offline)

    def initialize_report(self):
        """Initializes an instance of `TestReport` to hold the current test information."""

        report_data = {
            "demo_dataset_url": self.demo_dataset_url,
            "demo_dataset_hash": self.demo_dataset_hash,
            "data_path": self.data_path,
            "labels_path": self.labels_path,
            "prepared_data_hash": self.data_uid,
            "data_preparation_mlcube": self.data_prep,
            "model": self.model,
            "data_evaluator_mlcube": self.evaluator,
        }
        self.report = TestReport(**report_data)

    def cached_results(self):
        """checks the existance of, and retrieves if possible, the compatibility test
        result. This method is called prior to the test execution.

        Returns:
            (dict|None): None if the results does not exist or if self.no_cache is True,
            otherwise it returns the found results.
        """
        if self.no_cache:
            return
        uid = self.report.generated_uid
        try:
            report = TestReport.get(uid)
        except InvalidArgumentError:
            return
        logging.info(f"Existing report {uid} was detected.")
        logging.info("The compatibilty test will not be re-executed.")
        return report.results

    def execute(self):
        """Runs the test execution flow and returns the results

        Returns:
            dict: returns the results of the test execution.
        """
        execution_summary = Execution.run(
            dataset=self.dataset,
            model=self.model_cube,
            evaluator=self.evaluator_cube,
            ignore_model_errors=False,
        )
        return execution_summary["results"]

    def write(self, results):
        """Writes a report of the test execution to the disk
        Args:
            results (dict): the results of the test execution
        """
        self.report.set_results(results)
        self.report.write()
