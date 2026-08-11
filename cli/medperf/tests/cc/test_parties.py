import pytest

from medperf.cc.parties import collector_key_hashes, party_owners
from medperf.tests.mocks.benchmark import TestBenchmark
from medperf.tests.mocks.dataset import TestDataset
from medperf.tests.mocks.model import TestAssetModel
from medperf_cc.policy import Party

PATCH_CC_PARTIES = "medperf.cc.parties.{}"

BENCHMARK_OWNER_ID = 10
DATA_OWNER_ID = 20
MODEL_OWNER_ID = 30


@pytest.fixture()
def owners():
    return party_owners(
        TestBenchmark(owner=BENCHMARK_OWNER_ID),
        dataset=TestDataset(owner=DATA_OWNER_ID),
        model=TestAssetModel(owner=MODEL_OWNER_ID),
    )


def test_every_role_maps_to_the_user_that_holds_it(owners):
    # Assert
    assert owners == {
        Party.BENCHMARK_OWNER: BENCHMARK_OWNER_ID,
        Party.DATA_OWNER: DATA_OWNER_ID,
        Party.MODEL_OWNER: MODEL_OWNER_ID,
    }


def test_an_absent_peer_holds_no_role():
    """A grant that does not pin the peer asset is built without one"""
    # Act
    owners = party_owners(TestBenchmark(owner=BENCHMARK_OWNER_ID))

    # Assert
    assert owners == {Party.BENCHMARK_OWNER: BENCHMARK_OWNER_ID}


def test_naming_no_collector_leaves_the_term_empty(owners):
    """An owner who does not pin the collector grants one identity, and it
    carries an empty collector hash"""
    # Act & Assert
    assert collector_key_hashes([], owners) == [""]


def test_each_named_collector_becomes_its_own_key_hash(mocker, owners):
    # Arrange
    mocker.patch(
        PATCH_CC_PARTIES.format("owner_key_hash"),
        side_effect=lambda owner_id: f"hash-of-{owner_id}",
    )

    # Act
    hashes = collector_key_hashes([Party.DATA_OWNER, Party.BENCHMARK_OWNER], owners)

    # Assert
    assert hashes == [f"hash-of-{DATA_OWNER_ID}", f"hash-of-{BENCHMARK_OWNER_ID}"]


def test_a_collector_without_a_certificate_is_skipped(mocker, owners):
    """A party holding no key cannot receive results, so there is no identity
    to grant for them"""
    # Arrange
    mocker.patch(PATCH_CC_PARTIES.format("owner_key_hash"), return_value=None)

    # Act & Assert
    assert collector_key_hashes([Party.DATA_OWNER], owners) == []
