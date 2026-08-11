import pytest

from medperf.cc.workloads import (
    dedup_workloads,
    get_approved_component_ids,
    get_associated_benchmarks,
    get_confidential_plan,
)
from medperf.enums import BenchmarkTopology
from medperf.tests.mocks.benchmark import TestBenchmark
from medperf.tests.mocks.cube import TestCube
from medperf_cc.gcp import CCWorkloadID

PATCH_CC_WORKLOADS = "medperf.cc.workloads.{}"


def workload(script_hash="s", model_hash="m", data_hash="d", collector_hash="c"):
    return CCWorkloadID(
        script_hash=script_hash,
        model_hash=model_hash,
        data_hash=data_hash,
        result_collector_hash=collector_hash,
        model_id=1,
        script_id=2,
        data_id=3,
    )


def test_dedup_workloads_collapses_repeated_identities():
    # Arrange
    workloads = [workload(), workload(), workload(data_hash="other")]

    # Act
    deduped = dedup_workloads(workloads)

    # Assert
    assert len(deduped) == 2


def test_dedup_workloads_for_model_ignores_data_and_collector():
    """A model-side grant only pins the script and the model, so two workloads
    that differ only in data collapse into one principal"""
    # Arrange
    workloads = [workload(), workload(data_hash="other", collector_hash="other")]

    # Act
    deduped = dedup_workloads(workloads, for_model=True)

    # Assert
    assert len(deduped) == 1


@pytest.mark.parametrize("component_type", ["model", "dataset"])
def test_associated_benchmarks_only_uses_approved_associations(mocker, component_type):
    # Arrange
    spy = mocker.patch(
        PATCH_CC_WORKLOADS.format("get_component_associations"), return_value=[]
    )

    # Act
    get_associated_benchmarks(7, component_type)

    # Assert
    spy.assert_called_once_with(
        component_id=7,
        component_type=component_type,
        experiment_type="benchmark",
        approval_status="APPROVED",
    )


def test_approved_component_ids_only_uses_approved_associations(mocker):
    # Arrange
    spy = mocker.patch(
        PATCH_CC_WORKLOADS.format("get_experiment_associations"),
        return_value=[{"model": 3}, {"model": 5}],
    )

    # Act
    ids = get_approved_component_ids(9, "model")

    # Assert
    spy.assert_called_once_with(
        experiment_id=9,
        experiment_type="benchmark",
        component_type="model",
        approval_status="APPROVED",
    )
    assert ids == [3, 5]


def test_confidential_plan_is_absent_for_container_model_benchmarks():
    # Arrange
    benchmark = TestBenchmark(topology=BenchmarkTopology.BYO_INFERENCE_SCRIPT.value)

    # Act & Assert
    assert get_confidential_plan(benchmark) is None


def test_confidential_plan_is_resolved_for_script_benchmarks(mocker):
    # Arrange
    mocker.patch(
        "medperf.commands.execution.plan.Cube.get", return_value=TestCube(id=7)
    )
    benchmark = TestBenchmark(
        topology=BenchmarkTopology.END_TO_END_SCRIPT.value,
        data_evaluator_mlcube=None,
        benchmark_script=7,
    )

    # Act
    plan = get_confidential_plan(benchmark)

    # Assert
    assert plan.script.id == 7
    assert plan.evaluator is None
