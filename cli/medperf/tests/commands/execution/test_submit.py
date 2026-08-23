from medperf.exceptions import CleanExit
import pytest

from medperf.tests.mocks.execution import TestExecution
from medperf.tests.mocks.dataset import TestDataset

from medperf.commands.execution.submit import ResultSubmission

PATCH_SUBMISSION = "medperf.commands.execution.submit.{}"


@pytest.fixture(autouse=True)
def an_ordinary_execution(mocker):
    """Not confidential, so nobody but its owner was ever going to report it.

    Whether a confidential execution's results are somebody else's to report
    is decided by the asset owners' policies, and covered in
    `tests/cc/test_collector.py`."""
    mocker.patch(
        PATCH_SUBMISSION.format("Model.get"),
        return_value=mocker.MagicMock(**{"requires_cc.return_value": False}),
    )


@pytest.fixture
def result(fs):
    exec = TestExecution()
    exec.write()
    exec.save_results({}, False)
    exec.mark_as_executed()
    return exec


@pytest.fixture
def dataset():
    return TestDataset(id=1)


@pytest.fixture
def submission(mocker, comms, ui, result, dataset):
    mocker.patch(PATCH_SUBMISSION.format("Execution.all"), return_value=[result])
    mocker.patch(
        PATCH_SUBMISSION.format("get_medperf_user_data"), return_value={"id": 1}
    )
    mocker.patch(
        PATCH_SUBMISSION.format("filter_latest_executions"), side_effect=lambda x: x
    )
    sub = ResultSubmission(None, 1, 1, 1)
    sub.get_execution()
    sub.prepare()
    return sub


def test_upload_results_requests_approval(mocker, submission, result):
    # Arrange
    spy = mocker.patch(PATCH_SUBMISSION.format("approval_prompt"), return_value=True)
    mocker.patch(PATCH_SUBMISSION.format("ResultSubmission.write"))

    # Act
    ResultSubmission.run(None, 1, 1, 1)

    # Assert
    spy.assert_called_once()


@pytest.mark.parametrize("approved", [True, False])
def test_upload_results_fails_if_not_approved(mocker, submission, result, approved):
    # Arrange
    mocker.patch(PATCH_SUBMISSION.format("approval_prompt"), return_value=approved)

    # Act & Assert
    if approved:
        submission.update_execution()
    else:
        with pytest.raises(CleanExit):
            submission.update_execution()


def test_run_executes_upload_procedure(mocker, comms, ui, submission):
    # Arrange
    up_spy = mocker.spy(ResultSubmission, "update_execution")
    write_spy = mocker.patch(PATCH_SUBMISSION.format("ResultSubmission.write"))

    mocker.patch.object(ui, "prompt", return_value="y")

    # Act
    ResultSubmission.run(None, 1, 1, 1)

    # Assert
    up_spy.assert_called_once()
    write_spy.assert_called_once()


def test_write_writes_results_using_entity(mocker, submission, result, fs):
    # Arrange
    spy = mocker.patch(PATCH_SUBMISSION.format("Execution.get"), return_value=result)

    # Act
    submission.write()

    # Assert
    spy.assert_called()


def test_the_integrity_proof_goes_up_with_the_results(mocker, ui):
    """Otherwise the server holds a number nobody but its collector could ever
    check, and verifying it needs the machine that collected it"""
    # Arrange
    execution = TestExecution(id=1)
    mocker.patch(PATCH_SUBMISSION.format("Execution.get"), return_value=execution)
    mocker.patch.object(execution, "read_results", return_value={"auc": 0.9})
    mocker.patch.object(execution, "is_partial", return_value=False)
    mocker.patch.object(execution, "is_executed", return_value=True)
    mocker.patch.object(
        execution, "read_integrity_proof", return_value={"statement": {}, "token": "t"}
    )
    mocker.patch.object(execution, "write")
    update = mocker.patch(PATCH_SUBMISSION.format("config.comms.update_execution"))

    # Act
    ResultSubmission.run(1, approved=True)

    # Assert
    body = update.call_args.args[1]
    assert body["integrity_proof"] == {"statement": {}, "token": "t"}


def test_an_execution_without_a_proof_sends_no_proof_field(mocker, ui):
    """An unverifiable execution says so by the field being absent, not by an
    empty one that looks like a proof that failed"""
    # Arrange
    execution = TestExecution(id=1)
    mocker.patch(PATCH_SUBMISSION.format("Execution.get"), return_value=execution)
    mocker.patch.object(execution, "read_results", return_value={"auc": 0.9})
    mocker.patch.object(execution, "is_partial", return_value=False)
    mocker.patch.object(execution, "is_executed", return_value=True)
    mocker.patch.object(execution, "read_integrity_proof", return_value={})
    mocker.patch.object(execution, "write")
    update = mocker.patch(PATCH_SUBMISSION.format("config.comms.update_execution"))

    # Act
    ResultSubmission.run(1, approved=True)

    # Assert
    assert "integrity_proof" not in update.call_args.args[1]


def test_results_written_for_somebody_else_are_not_reported_here(mocker, ui):
    """`medperf run` submits as soon as it finishes. An operator who is not
    the collector holds nothing -- reporting it would upload empty results and
    finalize the execution, locking out the one party who can fill it in"""
    # Arrange
    execution = TestExecution(id=1)
    mocker.patch(PATCH_SUBMISSION.format("Execution.get"), return_value=execution)
    mocker.patch(
        PATCH_SUBMISSION.format("Model.get"),
        return_value=mocker.MagicMock(**{"requires_cc.return_value": True}),
    )
    mocker.patch(PATCH_SUBMISSION.format("Benchmark.get"))
    mocker.patch(PATCH_SUBMISSION.format("Dataset.get"))
    mocker.patch(
        PATCH_SUBMISSION.format("collector_role"), return_value=(999, "data_owner")
    )
    mocker.patch(
        PATCH_SUBMISSION.format("get_medperf_user_data"), return_value={"id": 1}
    )
    update = mocker.patch(PATCH_SUBMISSION.format("config.comms.update_execution"))

    # Act & Assert
    with pytest.raises(CleanExit, match="written for somebody else"):
        ResultSubmission.run(1, approved=True)
    update.assert_not_called()


def test_the_collector_reports_their_own_confidential_results(mocker, ui):
    # Arrange
    execution = TestExecution(id=1)
    mocker.patch(PATCH_SUBMISSION.format("Execution.get"), return_value=execution)
    mocker.patch(
        PATCH_SUBMISSION.format("Model.get"),
        return_value=mocker.MagicMock(**{"requires_cc.return_value": True}),
    )
    mocker.patch(PATCH_SUBMISSION.format("Benchmark.get"))
    mocker.patch(PATCH_SUBMISSION.format("Dataset.get"))
    mocker.patch(
        PATCH_SUBMISSION.format("collector_role"), return_value=(1, "data_owner")
    )
    mocker.patch(
        PATCH_SUBMISSION.format("get_medperf_user_data"), return_value={"id": 1}
    )
    mocker.patch.object(execution, "read_results", return_value={"auc": 0.9})
    mocker.patch.object(execution, "is_partial", return_value=False)
    mocker.patch.object(execution, "is_executed", return_value=True)
    mocker.patch.object(execution, "read_integrity_proof", return_value={})
    mocker.patch.object(execution, "write")
    update = mocker.patch(PATCH_SUBMISSION.format("config.comms.update_execution"))

    # Act
    ResultSubmission.run(1, approved=True)

    # Assert
    update.assert_called_once()
