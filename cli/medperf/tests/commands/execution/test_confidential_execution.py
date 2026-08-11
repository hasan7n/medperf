import pytest

from medperf.commands.execution.confidential_execution import ConfidentialExecution
from medperf.commands.execution.confidential_model_container_execution import (
    ConfidentialModelContainerExecution,
)
from medperf.commands.execution.plan import BenchmarkPlan
from medperf.enums import BenchmarkTopology
from medperf.exceptions import ExecutionError
from medperf.tests.mocks.cube import TestCube

DATA_OWNER_ID = 20


@pytest.fixture()
def configured(mocker):
    """A dataset, a model and an operator all set up for confidential computing.

    `check_operator_is_allowed` is left out by giving the plan no benchmark,
    which is how a compatibility test runs: no associations, so no roles."""

    def entity(**kwargs):
        return mocker.MagicMock(**{"is_cc_configured.return_value": True}, **kwargs)

    return {
        "dataset": entity(id=1, owner=DATA_OWNER_ID),
        "model": entity(id=2),
        "operator": entity(id=DATA_OWNER_ID),
    }


def plan_for(topology):
    return BenchmarkPlan(
        topology=topology,
        benchmark_id=None,
        script=TestCube(id=7),
        evaluator=TestCube(id=8) if topology.requires_evaluator else None,
    )


def flow_for(cls, topology, configured):
    flow = cls(plan_for(topology), configured["dataset"], configured["model"])
    flow.operator = configured["operator"]
    return flow


def test_predictions_scored_on_prem_need_the_data_owner(mocker, configured):
    """An inference_script benchmark scores its predictions against ground
    truth labels nobody but the data owner holds"""
    # Arrange
    configured["operator"] = mocker.MagicMock(
        id=99, **{"is_cc_configured.return_value": True}
    )
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
    configured["operator"] = mocker.MagicMock(
        id=99, **{"is_cc_configured.return_value": True}
    )
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
    configured[unconfigured].is_cc_configured.return_value = False
    flow = flow_for(
        ConfidentialExecution, BenchmarkTopology.END_TO_END_SCRIPT, configured
    )

    # Act & Assert
    with pytest.raises(ExecutionError):
        flow.validate()
