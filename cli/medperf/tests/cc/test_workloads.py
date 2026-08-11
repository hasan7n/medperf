import pytest

from medperf.cc.workloads import (
    __peer_datasets,
    __peer_models,
    get_approved_component_ids,
    get_associated_benchmarks,
    get_confidential_plan,
)
from medperf.enums import BenchmarkTopology
from medperf.tests.mocks.benchmark import TestBenchmark
from medperf.tests.mocks.cube import TestCube
from medperf_cc import AssetKind
from medperf_cc import AssetPolicy

PATCH_CC_WORKLOADS = "medperf.cc.workloads.{}"


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


@pytest.mark.parametrize(
    "kind,binds_peer", [(AssetKind.DATA, True), (AssetKind.MODEL, False)]
)
def test_a_grant_that_pins_no_peer_enumerates_none(mocker, kind, binds_peer):
    """The same grant covers every peer, so there is nothing to name"""
    # Arrange
    spy = mocker.patch(PATCH_CC_WORKLOADS.format("get_approved_component_ids"))
    policy = AssetPolicy(bind_peer_asset=False)
    peers = __peer_models if kind is AssetKind.DATA else __peer_datasets

    # Act
    result = peers(TestBenchmark(), policy)

    # Assert
    assert result == [None]
    spy.assert_not_called()


def test_a_data_owner_pinning_the_model_skips_models_that_are_not_confidential(mocker):
    # Arrange
    mocker.patch(
        PATCH_CC_WORKLOADS.format("get_approved_component_ids"), return_value=[1, 2]
    )
    confidential = mocker.MagicMock(**{"requires_cc.return_value": True})
    plain = mocker.MagicMock(**{"requires_cc.return_value": False})
    mocker.patch(
        PATCH_CC_WORKLOADS.format("Model.get"),
        side_effect=lambda model_id: confidential if model_id == 1 else plain,
    )

    # Act
    models = __peer_models(TestBenchmark(), AssetPolicy(bind_peer_asset=True))

    # Assert
    assert models == [confidential]
