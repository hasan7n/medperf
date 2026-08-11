"""Turning benchmark associations into permitted workload identities.

A confidential computing policy answers one question: which workloads may
decrypt this asset? Both sides build that answer out of benchmark associations,
and what each of them has to enumerate follows from the terms its owner pins:
an owner who does not pin the peer asset grants the same identity for every
peer, so there is nothing to enumerate.
"""

from typing import List, Optional

from medperf.cc.config import policy_of
from medperf.cc.parties import collector_key_hashes, party_owners
from medperf.commands.association.utils import (
    get_component_associations,
    get_experiment_associations,
)
from medperf.commands.execution.plan import BenchmarkPlan, resolve_plan
from medperf.entities.benchmark import Benchmark
from medperf.entities.dataset import Dataset
from medperf.entities.model import Model
from medperf.enums import Status
from medperf_cc import AssetKind, WorkloadIdentity
from medperf_cc import AssetPolicy


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


def get_dataset_workloads(dataset: Dataset) -> List[WorkloadIdentity]:
    """The workloads a data owner authorizes to read their data."""
    policy = policy_of(dataset)
    collectors = policy.result_collectors(AssetKind.DATA)

    workloads = []
    for benchmark in get_associated_benchmarks(dataset.id, "dataset"):
        plan = get_confidential_plan(benchmark)
        if plan is None:
            continue
        for model in __peer_models(benchmark, policy):
            owners = party_owners(benchmark, dataset=dataset, model=model)
            for collector_hash in collector_key_hashes(collectors, owners):
                workloads.append(
                    WorkloadIdentity(
                        data_hash=dataset.generated_uid,
                        model_hash=model.asset_obj.asset_hash if model else "",
                        script_hash=plan.script_hash,
                        result_collector_hash=collector_hash,
                        data_id=dataset.id,
                        model_id=model.id if model else None,
                        script_id=plan.script_id,
                    )
                )
    return workloads


def get_model_workloads(model: Model) -> List[WorkloadIdentity]:
    """The workloads a model owner authorizes to load their weights."""
    policy = policy_of(model)
    collectors = policy.result_collectors(AssetKind.MODEL)
    asset_hash = model.asset_obj.asset_hash

    workloads = []
    for benchmark in get_associated_benchmarks(model.id, "model"):
        plan = get_confidential_plan(benchmark)
        if plan is None:
            continue
        for dataset in __peer_datasets(benchmark, policy):
            owners = party_owners(benchmark, dataset=dataset, model=model)
            for collector_hash in collector_key_hashes(collectors, owners):
                workloads.append(
                    WorkloadIdentity(
                        data_hash=dataset.generated_uid if dataset else "",
                        model_hash=asset_hash,
                        script_hash=plan.script_hash,
                        result_collector_hash=collector_hash,
                        data_id=dataset.id if dataset else None,
                        model_id=model.id,
                        script_id=plan.script_id,
                    )
                )
    return workloads


def __peer_models(benchmark: Benchmark, policy: AssetPolicy) -> List[Optional[Model]]:
    """The models a data owner's grant has to name, one at a time.

    A grant that does not pin the model is the same grant whichever model runs,
    so there is nothing to enumerate: None stands for "any"."""
    if not policy.binds_peer_asset(AssetKind.DATA):
        return [None]

    models = [
        Model.get(model_id)
        for model_id in get_approved_component_ids(benchmark.id, "model")
    ]
    return [model for model in models if model.requires_cc()]


def __peer_datasets(
    benchmark: Benchmark, policy: AssetPolicy
) -> List[Optional[Dataset]]:
    """The datasets a model owner's grant has to name, one at a time."""
    if not policy.binds_peer_asset(AssetKind.MODEL):
        return [None]

    return [
        Dataset.get(dataset_id)
        for dataset_id in get_approved_component_ids(benchmark.id, "dataset")
    ]
