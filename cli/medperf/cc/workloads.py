"""Turning benchmark associations into permitted workload identities.

A confidential computing policy answers one question: which workloads may
decrypt this asset? Both the dataset-side and the model-side policy build that
answer out of benchmark associations, so the rules for reading those
associations and for turning them into workload identities live here once.
"""

import base64
from typing import List

from medperf.commands.association.utils import (
    get_component_associations,
    get_experiment_associations,
)
from medperf.commands.execution.plan import BenchmarkPlan, resolve_plan
from medperf.entities.benchmark import Benchmark
from medperf.entities.certificate import Certificate
from medperf.enums import Status
from medperf.utils import get_string_hash


def get_associated_benchmarks(component_id: int, component_type: str) -> List[Benchmark]:
    """The benchmarks a dataset or a model is *approved* to take part in.

    Only approved, current associations are considered. A pending request has
    not been granted yet and a rejected or superseded one has been taken away,
    and neither should hand out decryption rights."""
    assocs = get_component_associations(
        component_id=component_id,
        component_type=component_type,
        experiment_type="benchmark",
        approval_status=Status.APPROVED.value,
    )
    return [Benchmark.get(assoc["benchmark"]) for assoc in assocs]


def get_approved_component_ids(benchmark_id: int, component_type: str) -> List[int]:
    """The datasets or models *approved* to take part in a benchmark."""
    assocs = get_experiment_associations(
        experiment_id=benchmark_id,
        experiment_type="benchmark",
        component_type=component_type,
        approval_status=Status.APPROVED.value,
    )
    return [assoc[component_type] for assoc in assocs]


def get_confidential_plan(benchmark: Benchmark) -> BenchmarkPlan:
    """The resolved plan of a benchmark that can host confidential workloads.

    Returns None for benchmarks whose topology has no benchmark script: those
    run container models, which are never loaded into a confidential VM."""
    if not benchmark.topology_enum.requires_benchmark_script:
        return None
    return resolve_plan(benchmark)


def public_key_hash(certificate: Certificate) -> str:
    """The result collector identity a workload attests with."""
    public_key_b64 = base64.b64encode(certificate.public_key())
    return get_string_hash(public_key_b64)
