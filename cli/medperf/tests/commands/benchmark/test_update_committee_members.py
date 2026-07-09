from medperf.exceptions import InvalidArgumentError
import pytest

from medperf.commands.benchmark.update_committee_members import UpdateCommitteeMembers


def test_both_file_and_list_raises():
    # Act & Assert
    with pytest.raises(InvalidArgumentError):
        UpdateCommitteeMembers(
            1,
            committee_emails_file="/somefile",
            committee_emails="test@example.com",
        ).validate()


def test_committee_email_list_filled(mocker, fs):
    # Arrange
    file = "/somefile"
    fs.create_file(file, contents="test@example.com\nmember@org.com")
    obj = UpdateCommitteeMembers(1, committee_emails_file=file)

    # Act
    obj.read_emails()
    obj.validate_emails()

    # Assert
    assert obj.committee_emails_list == ["test@example.com", "member@org.com"]


def test_invalid_email_list(mocker, fs):
    # Arrange
    file = "/somefile"
    fs.create_file(file, contents="invalidemail\nmember@org.com")
    obj = UpdateCommitteeMembers(1, committee_emails_file=file)
    obj.read_emails()

    # Act & Assert
    with pytest.raises(InvalidArgumentError):
        obj.validate_emails()


def test_update_calls_comms_with_file_emails(mocker, comms):
    # Arrange
    spy = mocker.patch.object(comms, "update_benchmark")
    obj = UpdateCommitteeMembers(1)
    obj.committee_emails_list = ["test@example.com", "member@org.com"]

    # Act
    obj.update()

    # Assert
    spy.assert_called_once_with(
        1,
        {"committee_member_emails": ["test@example.com", "member@org.com"]},
    )


def test_update_calls_comms_with_inline_emails(mocker, comms):
    # Arrange
    spy = mocker.patch.object(comms, "update_benchmark")
    obj = UpdateCommitteeMembers(
        1, committee_emails="member@example.com other@example.com"
    )
    obj.read_emails()
    obj.validate_emails()

    # Act
    obj.update()

    # Assert
    spy.assert_called_once_with(
        1,
        {"committee_member_emails": ["member@example.com", "other@example.com"]},
    )


def test_update_fails_when_no_emails_provided(mocker, comms):
    # Arrange
    obj = UpdateCommitteeMembers(1)

    # Act & Assert
    with pytest.raises(InvalidArgumentError):
        obj.validate()


def test_update_clears_members_with_empty_list(mocker, comms):
    # Arrange
    spy = mocker.patch.object(comms, "update_benchmark")
    obj = UpdateCommitteeMembers(1, committee_emails="")
    obj.read_emails()
    obj.validate_emails()

    # Act
    obj.update()

    # Assert
    spy.assert_called_once_with(1, {"committee_member_emails": []})
