from medperf.exceptions import InvalidArgumentError


class CompatibilityTestParamsValidator:
    def __validate_cubes(self):
        if not self.model and not self.benchmark_uid:
            raise InvalidArgumentError(
                "A model mlcube or a benchmark should at least be specified"
            )

        if not self.evaluator and not self.benchmark_uid:
            raise InvalidArgumentError(
                "A metrics mlcube or a benchmark should at least be specified"
            )

    def __raise_redundant_data_source(self):
        msg = "Make sure you pass only one data source: "
        msg += "either a prepared dataset, a data path and labels path, or a demo dataset url"
        raise InvalidArgumentError(msg)

    def __validate_prepared_data_source(self):
        if any(
            [
                self.data_path,
                self.labels_path,
                self.demo_dataset_url,
                self.demo_dataset_hash,
            ]
        ):
            self.__raise_redundant_data_source()
        if self.data_prep:
            raise InvalidArgumentError(
                "A data preparation cube is not needed when specifying a prepared dataset"
            )

    def __validate_data_path_source(self):
        if not self.labels_path:
            raise InvalidArgumentError(
                "Labels path should be specified when providing data path"
            )
        if any([self.demo_dataset_url, self.demo_dataset_hash, self.data_uid]):
            self.__raise_redundant_data_source()

        if not self.data_prep or not self.benchmark_uid:
            raise InvalidArgumentError(
                "A data preparation cube should be passed when specifying raw data input"
            )

    def __validate_demo_data_source(self):
        if any([self.data_path, self.labels_path, self.data_uid]):
            self.__raise_redundant_data_source()

        if not self.data_prep or not self.benchmark_uid:
            raise InvalidArgumentError(
                "A data preparation cube should be passed when specifying raw data input"
            )

    def __validate_data_source(self):
        if not any([self.data_path, self.demo_dataset_url, self.data_uid]):
            if not self.benchmark_uid:
                msg = "A data source should at least be specified, either by providing"
                msg += " a prepared data uid, a demo dataset url, data path, or a benchmark"
                raise InvalidArgumentError(msg)
            self.from_benchmark = True
            return

        if self.data_uid:
            self.__validate_prepared_data_source()
            self.from_prepared = True
            return

        if self.data_path:
            self.__validate_data_path_source()
            self.from_path = True
            return

        if self.demo_dataset_url:
            self.__validate_demo_data_source()
            self.from_demo = True
            return

    def __validate_redundant_benchmark(self):
        if self.benchmark_uid:
            if (
                not self.from_benchmark
                and self.model
                and self.evaluator
                and (self.from_prepared or self.data_prep)
            ):
                raise InvalidArgumentError("The provided benchmark will not be used")

    def validate(self):
        """Ensures test has been passed a valid combination of parameters.
        """

        self.__validate_cubes()
        self.__validate_data_source()
        self.__validate_redundant_benchmark()
