from medperf import config
from medperf.entities.cube import Cube
from medperf.entities.benchmark import Benchmark
from medperf.exceptions import CleanExit
from medperf.utils import dict_pretty_print, approval_prompt
from medperf.commands.compatibility_test.run import CompatibilityTestExecution


class AssociateCube:
    @classmethod
    def run(
        cls, cube_uid: int, benchmark_uid: int, approved=False, no_cache=False,
    ):
        """Associates a cube with a given benchmark

        Args:
            cube_uid (int): UID of model MLCube
            benchmark_uid (int): UID of benchmark
            approved (bool): Skip validation step. Defualts to False
        """
        comms = config.comms
        ui = config.ui
        cube = Cube.get(cube_uid)
        benchmark = Benchmark.get(benchmark_uid)

        _, _, _, results = CompatibilityTestExecution.run(
            benchmark_uid, model=cube_uid, no_cache=no_cache
        )
        ui.print("These are the results generated by the compatibility test. ")
        ui.print("This will be sent along the association request.")
        ui.print("They will not be part of the benchmark.")
        dict_pretty_print(results)

        msg = "Please confirm that you would like to associate "
        msg += f"the MLCube '{cube.name}' with the benchmark '{benchmark.name}' [Y/n]"
        approved = approved or approval_prompt(msg)
        if approved:
            ui.print("Generating mlcube benchmark association")
            metadata = {"test_result": results}
            comms.associate_cube(cube_uid, benchmark_uid, metadata)
        else:
            raise CleanExit("MLCube association operation cancelled")
