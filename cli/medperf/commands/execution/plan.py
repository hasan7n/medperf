"""Resolution of *what* a benchmark execution is made of, separately from
*where* it runs.

Two orthogonal questions decide how a benchmark is executed:

- the **topology** (`BenchmarkTopology`): who produces the predictions and who
  evaluates them. A property of the benchmark.
- the **execution medium** (`ExecutionMedium`): whether the model runs locally
  or inside a confidential VM. A property of the model and the operator.

This module answers both once, so that every consumer — the execution flow, the
compatibility test and the confidential computing policies — agrees on which
container image is the one that actually runs.
"""

from dataclasses import dataclass
from typing import Optional

from medperf.account_management import get_medperf_user_data, is_user_logged_in
from medperf.entities.benchmark import Benchmark
from medperf.entities.cube import Cube
from medperf.entities.model import Model
from medperf.enums import BenchmarkTopology, ExecutionMedium
from medperf.exceptions import InvalidArgumentError


@dataclass(frozen=True)
class BenchmarkPlan:
    """The resolved, ready-to-run components of a benchmark.

    Attributes:
        topology: the benchmark's topology.
        benchmark_id: the benchmark this plan came from, if any. Compatibility
            tests build plans out of ad-hoc components and leave this unset.
        script: the benchmark-owned container that loads an asset model, if the
            topology has one. Its image hash is what a confidential workload
            attests with, which makes it the single trust anchor of the plan.
        evaluator: the container that computes the metrics, if the topology has
            a separate one.
    """

    topology: BenchmarkTopology
    benchmark_id: Optional[int] = None
    script: Optional[Cube] = None
    evaluator: Optional[Cube] = None

    @property
    def script_hash(self) -> str:
        """The image hash a confidential workload must attest with."""
        if self.script is None:
            raise InvalidArgumentError(
                f"A {self.topology.value} benchmark has no benchmark script"
            )
        return self.script.image_hash

    @property
    def script_id(self) -> int:
        if self.script is None:
            raise InvalidArgumentError(
                f"A {self.topology.value} benchmark has no benchmark script"
            )
        return self.script.id


def resolve_plan(benchmark: Benchmark) -> BenchmarkPlan:
    """Fetches the containers a benchmark's topology calls for.

    Containers are retrieved but not downloaded; callers that need to run them
    are responsible for calling `download_run_files`.
    """
    topology = benchmark.topology_enum
    script = None
    evaluator = None
    if topology.requires_benchmark_script:
        script = Cube.get(benchmark.benchmark_script)
    if topology.requires_evaluator:
        evaluator = Cube.get(benchmark.data_evaluator_mlcube)
    return BenchmarkPlan(
        topology=topology,
        benchmark_id=benchmark.id,
        script=script,
        evaluator=evaluator,
    )


def resolve_execution_medium(model: Model) -> ExecutionMedium:
    """Decides whether a model runs locally or in a confidential VM.

    A model owner always runs their own model locally: they already hold the
    weights, so there is nothing to protect them from.
    """
    if not model.requires_cc():
        return ExecutionMedium.LOCAL

    user_is_model_owner = (
        is_user_logged_in() and model.owner == get_medperf_user_data()["id"]
    )
    if user_is_model_owner:
        return ExecutionMedium.LOCAL

    return ExecutionMedium.CONFIDENTIAL
