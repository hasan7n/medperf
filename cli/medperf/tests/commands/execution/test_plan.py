import pytest

from medperf.commands.execution.execution_flow import ExecutionFlow
from medperf.commands.execution.plan import (
    BenchmarkPlan,
    resolve_execution_medium,
    resolve_plan,
)
from medperf.enums import BenchmarkTopology, ExecutionMedium
from medperf.exceptions import ExecutionError, InvalidArgumentError
from medperf.tests.mocks.benchmark import TestBenchmark
from medperf.tests.mocks.cube import TestCube
from medperf.tests.mocks.dataset import TestDataset
from medperf.tests.mocks.model import TestAssetModel, TestContainerModel

PATCH_PLAN = "medperf.commands.execution.plan.{}"
PATCH_FLOW = "medperf.commands.execution.execution_flow.{}"


@pytest.fixture()
def cubes(mocker):
    """Cube.get returns a cube whose id matches the requested uid"""
    cubes = {}

    def _get(uid, *args, **kwargs):
        cubes.setdefault(uid, TestCube(id=uid))
        return cubes[uid]

    mocker.patch(PATCH_PLAN.format("Cube.get"), side_effect=_get)
    return cubes


@pytest.mark.parametrize(
    "topology,expected_script,expected_evaluator",
    [
        (BenchmarkTopology.BYO_INFERENCE_SCRIPT, None, 3),
        (BenchmarkTopology.END_TO_END_SCRIPT, 7, None),
        (BenchmarkTopology.INFERENCE_SCRIPT, 7, 3),
    ],
)
def test_resolve_plan_fetches_what_the_topology_needs(
    cubes, topology, expected_script, expected_evaluator
):
    # Arrange
    benchmark = TestBenchmark(
        topology=topology.value,
        data_evaluator_mlcube=3 if topology.requires_evaluator else None,
        benchmark_script=7 if topology.requires_benchmark_script else None,
    )

    # Act
    plan = resolve_plan(benchmark)

    # Assert
    assert plan.topology == topology
    assert plan.benchmark_id == benchmark.id
    assert (plan.script.id if plan.script else None) == expected_script
    assert (plan.evaluator.id if plan.evaluator else None) == expected_evaluator


def test_script_hash_of_a_scriptless_topology_is_an_error():
    # Arrange
    plan = BenchmarkPlan(topology=BenchmarkTopology.BYO_INFERENCE_SCRIPT)

    # Act & Assert
    with pytest.raises(InvalidArgumentError):
        plan.script_hash


@pytest.mark.parametrize(
    "requires_cc,is_owner,expected",
    [
        (False, False, ExecutionMedium.LOCAL),
        (False, True, ExecutionMedium.LOCAL),
        (True, True, ExecutionMedium.LOCAL),
        (True, False, ExecutionMedium.CONFIDENTIAL),
    ],
)
def test_resolve_execution_medium(mocker, requires_cc, is_owner, expected):
    # Arrange
    model = TestAssetModel(owner=1)
    mocker.patch.object(model, "requires_cc", return_value=requires_cc)
    mocker.patch(PATCH_PLAN.format("is_user_logged_in"), return_value=True)
    mocker.patch(
        PATCH_PLAN.format("get_medperf_user_data"),
        return_value={"id": 1 if is_owner else 99},
    )

    # Act
    medium = resolve_execution_medium(model)

    # Assert
    assert medium == expected


@pytest.mark.parametrize(
    "topology,medium,executor",
    [
        (BenchmarkTopology.BYO_INFERENCE_SCRIPT, ExecutionMedium.LOCAL, "container"),
        (BenchmarkTopology.END_TO_END_SCRIPT, ExecutionMedium.LOCAL, "script"),
        (
            BenchmarkTopology.END_TO_END_SCRIPT,
            ExecutionMedium.CONFIDENTIAL,
            "confidential",
        ),
        (
            BenchmarkTopology.INFERENCE_SCRIPT,
            ExecutionMedium.CONFIDENTIAL,
            "confidential_container",
        ),
    ],
)
def test_supported_combinations_reach_their_executor(mocker, topology, medium, executor):
    """The dispatch table is what decides; the executors themselves are stubbed"""
    # Arrange
    names = {
        (BenchmarkTopology.BYO_INFERENCE_SCRIPT, ExecutionMedium.LOCAL): "container",
        (BenchmarkTopology.END_TO_END_SCRIPT, ExecutionMedium.LOCAL): "script",
        (
            BenchmarkTopology.END_TO_END_SCRIPT,
            ExecutionMedium.CONFIDENTIAL,
        ): "confidential",
        (
            BenchmarkTopology.INFERENCE_SCRIPT,
            ExecutionMedium.CONFIDENTIAL,
        ): "confidential_container",
    }
    spies = {name: mocker.MagicMock() for name in names.values()}
    mocker.patch.dict(
        PATCH_FLOW.format("EXECUTORS"),
        {key: spies[name] for key, name in names.items()},
        clear=True,
    )
    mocker.patch(PATCH_FLOW.format("resolve_execution_medium"), return_value=medium)
    model = TestAssetModel() if topology.uses_asset_models else TestContainerModel()
    plan = BenchmarkPlan(topology=topology, script=TestCube(id=7))
    dataset = TestDataset()

    # Act
    ExecutionFlow.run(plan, dataset, model)

    # Assert
    spies[executor].assert_called_once_with(plan, dataset, model, None, False)
    for name, spy in spies.items():
        if name != executor:
            spy.assert_not_called()


@pytest.mark.parametrize(
    "topology,medium",
    [
        (BenchmarkTopology.BYO_INFERENCE_SCRIPT, ExecutionMedium.CONFIDENTIAL),
        (BenchmarkTopology.INFERENCE_SCRIPT, ExecutionMedium.LOCAL),
    ],
)
def test_unsupported_combinations_are_rejected(mocker, topology, medium):
    # Arrange
    mocker.patch(PATCH_FLOW.format("resolve_execution_medium"), return_value=medium)
    model = TestAssetModel() if topology.uses_asset_models else TestContainerModel()
    plan = BenchmarkPlan(topology=topology, script=TestCube(id=7))

    # Act & Assert
    with pytest.raises(ExecutionError):
        ExecutionFlow.run(plan, TestDataset(), model)


@pytest.mark.parametrize(
    "topology,model_factory",
    [
        (BenchmarkTopology.BYO_INFERENCE_SCRIPT, TestAssetModel),
        (BenchmarkTopology.END_TO_END_SCRIPT, TestContainerModel),
        (BenchmarkTopology.INFERENCE_SCRIPT, TestContainerModel),
    ],
)
def test_model_of_the_wrong_kind_is_rejected(topology, model_factory):
    # Arrange
    plan = BenchmarkPlan(topology=topology)

    # Act & Assert
    with pytest.raises(ExecutionError):
        ExecutionFlow.validate_model(plan, model_factory())
