import pytest

from medperf.commands.execution.confidential_execution import ConfidentialExecution
from medperf.commands.execution.confidential_model_container_execution import (
    ConfidentialModelContainerExecution,
)
from medperf.commands.execution.plan import BenchmarkPlan
from medperf.enums import BenchmarkTopology
from medperf.exceptions import ExecutionError
from medperf.tests.mocks.cube import TestCube

PATCH_FLOW = "medperf.commands.execution.confidential_execution.{}"
PATCH_CONTAINER_FLOW = (
    "medperf.commands.execution.confidential_model_container_execution.{}"
)

DATA_OWNER_ID = 20
BENCHMARK_ID = 11
EXECUTION_ID = 42


@pytest.fixture(autouse=True)
def collectors_accept_everyone(mocker):
    """Whether the asset owners release results to this operator is decided by
    their policies, and covered in `tests/cc/test_parties.py`. These tests are
    about the checks around it."""
    mocker.patch(PATCH_FLOW.format("check_operator_is_allowed"))
    mocker.patch(PATCH_CONTAINER_FLOW.format("check_operator_is_allowed"))


class FakeAsset:
    """A dataset or a model, asked only whether it is set up for CC.

    A real object rather than a Mock: an asset is asked `is_cc_configured` and
    a user is asked about one of their roles, so calling the wrong one has to
    fail here rather than quietly return something truthy."""

    def __init__(self, id, owner=None, cc_configured=True):
        self.id = id
        self.owner = owner
        self.cc_configured = cc_configured

    def is_cc_configured(self):
        return self.cc_configured


class FakeRole:
    def __init__(self, configured=True):
        self.configured = configured


class FakeUser:
    """An operator, asked about the roles they hold rather than about "CC"."""

    def __init__(self, id, cc_configured=True):
        self.id = id
        self.cc_operator = FakeRole(cc_configured)
        self.cc_collector = FakeRole(cc_configured)


@pytest.fixture()
def configured(mocker):
    """A dataset, a model and an operator all set up for confidential
    computing."""
    return {
        "dataset": FakeAsset(id=1, owner=DATA_OWNER_ID),
        "model": FakeAsset(id=2),
        "operator": FakeUser(id=DATA_OWNER_ID),
        "execution": mocker.MagicMock(id=EXECUTION_ID),
    }


def plan_for(topology):
    return BenchmarkPlan(
        topology=topology,
        benchmark_id=BENCHMARK_ID,
        script=TestCube(id=7),
        evaluator=TestCube(id=8) if topology.requires_evaluator else None,
    )


def flow_for(cls, topology, configured):
    flow = cls(
        plan_for(topology),
        configured["dataset"],
        configured["model"],
        configured["execution"],
    )
    flow.operator = configured["operator"]
    return flow


def test_predictions_scored_on_prem_need_the_data_owner(mocker, configured):
    """An inference_script benchmark scores its predictions against ground
    truth labels nobody but the data owner holds"""
    # Arrange
    configured["operator"] = FakeUser(id=99)
    flow = flow_for(
        ConfidentialModelContainerExecution,
        BenchmarkTopology.INFERENCE_SCRIPT,
        configured,
    )

    # Act & Assert
    with pytest.raises(ExecutionError, match="operated by the data owner"):
        flow.validate()


def test_the_data_owner_may_operate_their_own_inference_run(configured):
    # Arrange
    flow = flow_for(
        ConfidentialModelContainerExecution,
        BenchmarkTopology.INFERENCE_SCRIPT,
        configured,
    )

    # Act & Assert
    flow.validate()


def test_an_end_to_end_run_may_be_operated_by_anyone(mocker, configured):
    """The metric is computed inside the VM, so no on-prem labels are involved
    and there is nothing tying the run to the data owner"""
    # Arrange
    configured["operator"] = FakeUser(id=99)
    flow = flow_for(
        ConfidentialExecution, BenchmarkTopology.END_TO_END_SCRIPT, configured
    )

    # Act & Assert
    flow.validate()


@pytest.mark.parametrize("unconfigured", ["dataset", "model", "operator"])
def test_every_party_must_be_configured_for_confidential_computing(
    mocker, configured, unconfigured
):
    # Arrange
    party = configured[unconfigured]
    if isinstance(party, FakeUser):
        party.cc_operator = FakeRole(configured=False)
    else:
        party.cc_configured = False
    flow = flow_for(
        ConfidentialExecution, BenchmarkTopology.END_TO_END_SCRIPT, configured
    )

    # Act & Assert
    with pytest.raises(ExecutionError):
        flow.validate()


def test_results_are_not_collected_before_the_workload_has_finished(mocker, configured):
    """A runner starts a workload and returns; downloading straight away would
    fetch whatever happens to be there, which is nothing"""
    # Arrange
    flow = flow_for(
        ConfidentialExecution, BenchmarkTopology.END_TO_END_SCRIPT, configured
    )
    flow.runner = mocker.MagicMock()
    flow.result_store = mocker.MagicMock()
    flow.workload = mocker.MagicMock()
    order = []
    mocker.patch(
        PATCH_FLOW.format("wait_for_workload"),
        side_effect=lambda *a: order.append("wait"),
    )
    mocker.patch(
        PATCH_FLOW.format("results_exist"),
        side_effect=lambda *a: order.append("check") or True,
    )

    # Act
    flow.wait_for_workload_completion()

    # Assert
    assert order == ["wait", "check"]


def test_a_workload_that_produced_nothing_is_reported(mocker, configured):
    # Arrange
    flow = flow_for(
        ConfidentialExecution, BenchmarkTopology.END_TO_END_SCRIPT, configured
    )
    flow.runner = mocker.MagicMock()
    flow.result_store = mocker.MagicMock()
    flow.workload = mocker.MagicMock()
    mocker.patch(PATCH_FLOW.format("wait_for_workload"))
    mocker.patch(PATCH_FLOW.format("results_exist"), return_value=False)

    # Act & Assert
    with pytest.raises(ExecutionError, match="did not complete"):
        flow.wait_for_workload_completion()


@pytest.mark.parametrize(
    "cls,topology",
    [
        (ConfidentialExecution, BenchmarkTopology.END_TO_END_SCRIPT),
        (ConfidentialModelContainerExecution, BenchmarkTopology.INFERENCE_SCRIPT),
    ],
)
def test_a_launched_workload_says_which_execution_it_is(
    mocker, configured, cls, topology
):
    """Its storage prefix is built from this. Without it, two runs of the same
    dataset, model and script write to the same place and the second overwrites
    the first"""
    # Arrange
    flow = flow_for(cls, topology, configured)
    flow.asset = mocker.MagicMock(asset_hash="assethash")
    flow.plan = mocker.MagicMock(script_hash="scripthash", script_id=7)
    flow.dataset.generated_uid = "datahash"
    mocker.patch(PATCH_FLOW.format("collector_public_key"), return_value=b"key")
    mocker.patch(
        PATCH_CONTAINER_FLOW.format("collector_public_key"), return_value=b"key"
    )

    # Act
    flow.setup_workload()

    # Assert
    assert flow.workload.execution_id == EXECUTION_ID
    assert str(EXECUTION_ID) in flow.workload.results_path
