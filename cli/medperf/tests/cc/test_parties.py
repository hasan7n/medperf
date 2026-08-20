import pytest

from medperf.cc.parties import (
    owner_key_hash,
    peer_key_hashes,
    check_operator_is_allowed,
    collector_key_hashes,
    party_owners,
)
from medperf.exceptions import ExecutionError
from medperf.tests.mocks.benchmark import TestBenchmark
from medperf.tests.mocks.dataset import TestDataset
from medperf.tests.mocks.model import TestAssetModel
from medperf_cc import AssetKind, AssetPolicy, Party

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


def test_each_named_collector_becomes_its_own_key_hash(mocker, owners):
    # Arrange
    mocker.patch(
        PATCH_CC_PARTIES.format("owner_key_hash"),
        side_effect=lambda owner_id, peer_hashes: f"hash-of-{owner_id}",
    )

    # Act
    hashes = collector_key_hashes([Party.DATA_OWNER, Party.BENCHMARK_OWNER], owners, {})

    # Assert
    assert hashes == [f"hash-of-{DATA_OWNER_ID}", f"hash-of-{BENCHMARK_OWNER_ID}"]


def test_a_collector_without_a_certificate_is_skipped(mocker, owners):
    """A party holding no key cannot receive results, so there is no identity
    to grant for them"""
    # Arrange
    mocker.patch(PATCH_CC_PARTIES.format("owner_key_hash"), return_value=None)

    # Act & Assert
    assert collector_key_hashes([Party.DATA_OWNER], owners, {}) == []


@pytest.fixture()
def entities(mocker):
    """The three entities of one execution, with policies the tests set."""
    entities = {
        "benchmark": TestBenchmark(owner=BENCHMARK_OWNER_ID),
        "dataset": TestDataset(owner=DATA_OWNER_ID),
        "model": TestAssetModel(owner=MODEL_OWNER_ID),
    }
    mocker.patch(
        PATCH_CC_PARTIES.format("Benchmark.get"), return_value=entities["benchmark"]
    )
    return entities


def set_policies(mocker, dataset_policy, model_policy):
    mocker.patch(
        PATCH_CC_PARTIES.format("policy_of"),
        side_effect=lambda entity: (
            dataset_policy if isinstance(entity, TestDataset) else model_policy
        ),
    )


def test_an_operator_both_owners_named_is_accepted(mocker, entities):
    # Arrange
    set_policies(
        mocker,
        AssetPolicy(allowed_result_collectors=[Party.BENCHMARK_OWNER]),
        AssetPolicy(allowed_result_collectors=[Party.BENCHMARK_OWNER]),
    )

    # Act & Assert
    check_operator_is_allowed(
        BENCHMARK_OWNER_ID, 1, entities["dataset"], entities["model"]
    )


def test_the_operator_must_be_accepted_by_both_owners(mocker, entities):
    """Both keys are needed for the workload to run, so either owner refusing
    is enough to stop it"""
    # Arrange
    set_policies(
        mocker,
        AssetPolicy(
            allowed_result_collectors=[Party.DATA_OWNER, Party.BENCHMARK_OWNER]
        ),
        AssetPolicy(allowed_result_collectors=[Party.DATA_OWNER]),
    )

    # Act & Assert
    check_operator_is_allowed(DATA_OWNER_ID, 1, entities["dataset"], entities["model"])
    with pytest.raises(ExecutionError, match="model owner"):
        check_operator_is_allowed(
            BENCHMARK_OWNER_ID, 1, entities["dataset"], entities["model"]
        )


def test_an_operator_holding_no_role_is_refused(mocker, entities):
    # Arrange
    set_policies(
        mocker,
        AssetPolicy(allowed_result_collectors=[Party.DATA_OWNER]),
        AssetPolicy(allowed_result_collectors=[Party.MODEL_OWNER]),
    )

    # Act & Assert
    with pytest.raises(ExecutionError, match="dataset owner"):
        check_operator_is_allowed(99, 1, entities["dataset"], entities["model"])


def test_a_peers_key_hash_comes_from_the_benchmark_listing(mocker):
    """Nobody may read another user's certificate in general; what they may
    read is the certificates of the parties they share a benchmark with"""
    # Arrange
    mocker.patch(PATCH_CC_PARTIES.format("is_user_logged_in"), return_value=False)

    # Act
    found = owner_key_hash(MODEL_OWNER_ID, {MODEL_OWNER_ID: "hash-of-the-model-owner"})
    absent = owner_key_hash(99, {MODEL_OWNER_ID: "hash-of-the-model-owner"})

    # Assert
    assert found == "hash-of-the-model-owner"
    assert absent is None


@pytest.mark.parametrize(
    "peer,expected_call",
    [
        (AssetKind.MODEL, "Certificate.get_benchmark_models_certificates"),
        (AssetKind.DATA, "Certificate.get_benchmark_datasets_certificates"),
    ],
)
def test_each_side_reads_the_listing_it_is_allowed(mocker, peer, expected_call):
    """A data owner may read the model owners' certificates and vice versa.
    Asking for the wrong one is a 403"""
    # Arrange
    spy = mocker.patch(PATCH_CC_PARTIES.format(expected_call), return_value=([], {}))

    # Act
    peer_key_hashes(7, peer)

    # Assert
    spy.assert_called_once_with(7)
