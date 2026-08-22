"""A user's confidential-computing roles.

Operating a workload and receiving its results are separate roles, and the
point of telling them apart is that one user may hold either without the other.
"""

import pytest

from medperf.entities.user import User


def a_user(metadata=None):
    return User(
        id=1,
        username="someone",
        email="someone@example.com",
        first_name="Some",
        last_name="One",
        metadata=metadata if metadata is not None else {},
    )


def test_a_user_who_has_configured_nothing_holds_neither_role():
    user = a_user()

    assert not user.cc_operator.configured
    assert not user.cc_collector.configured
    assert user.cc_operator.config == {}


def test_each_role_is_configured_without_touching_the_other():
    """The case the split exists for: somebody who receives results but does
    not run workloads, or the other way round"""
    # Arrange
    user = a_user()

    # Act
    user.cc_collector.set({"backend": "gcp", "bucket": "theirs"})

    # Assert
    assert user.cc_collector.configured
    assert not user.cc_operator.configured


def test_configuring_a_role_marks_it_unverified_again():
    """New settings have not been checked against the cloud yet, and saying
    they have would hide a bucket the user cannot actually write to"""
    # Arrange
    user = a_user()
    user.cc_operator.set({"backend": "mock"})
    user.cc_operator.mark_initialized()

    # Act
    user.cc_operator.set({"backend": "mock", "root": "/somewhere/else"})

    # Assert
    assert not user.cc_operator.initialized


def test_a_role_that_holds_nothing_cannot_be_marked_verified():
    # Arrange
    user = a_user()

    # Act
    user.cc_collector.mark_initialized()

    # Assert
    assert not user.cc_collector.initialized


def test_marking_one_role_verified_leaves_the_other_alone():
    # Arrange
    user = a_user()
    user.cc_operator.set({"backend": "mock"})
    user.cc_collector.set({"backend": "mock"})

    # Act
    user.cc_operator.mark_initialized()

    # Assert
    assert user.cc_operator.initialized
    assert not user.cc_collector.initialized


@pytest.mark.parametrize("initialized", [True, False])
def test_a_user_configured_before_the_roles_were_split_is_still_an_operator(
    initialized,
):
    """Their one configuration was the operator's. Reading it only under the
    new name would leave them silently unconfigured, and their next run would
    say they had never set anything up"""
    # Arrange
    legacy = {"cc": {"config": {"backend": "gcp", "vm_name": "vm"}}}
    legacy["cc"]["initialized"] = initialized
    user = a_user(legacy)

    # Assert
    assert user.cc_operator.configured
    assert user.cc_operator.config == {"backend": "gcp", "vm_name": "vm"}
    assert user.cc_operator.initialized is initialized


def test_the_old_shape_is_not_read_as_a_place_to_receive_results():
    """It was the operator's alone -- a bucket they ran from is not a bucket
    somebody else agreed to have results written to"""
    # Arrange
    user = a_user({"cc": {"config": {"backend": "gcp", "bucket": "b"}}})

    # Assert
    assert not user.cc_collector.configured


def test_saving_rewrites_the_old_shape_into_the_new_one():
    # Arrange
    user = a_user({"cc": {"config": {"backend": "gcp"}, "initialized": True}})

    # Act
    user.cc_operator.set({"backend": "mock"})

    # Assert
    assert user.metadata["cc"]["operator"] == {"backend": "mock"}
    assert user.cc_operator.config == {"backend": "mock"}
    assert not user.cc_operator.initialized
