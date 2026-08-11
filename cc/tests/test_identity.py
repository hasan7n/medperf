import pytest

from medperf_cc.identity import (
    COLLECTOR_TERM,
    DATA_TERM,
    TERM_CLAIMS,
    TERM_FIELDS,
    TERM_ORDER,
    AssetKind,
    WorkloadBinding,
    WorkloadIdentity,
)


@pytest.fixture()
def workload():
    return WorkloadIdentity(
        script_hash="scripthash",
        data_hash="datahash",
        model_hash="modelhash",
        result_collector_hash="collectorhash",
        script_id=1,
        data_id=2,
        model_id=3,
    )


def test_every_term_has_a_claim_and_a_field():
    """The three tables are read together. A term missing from one of them
    would go unnoticed until an authorization silently stopped matching"""
    assert set(TERM_CLAIMS) == set(TERM_ORDER)
    assert set(TERM_FIELDS) == set(TERM_ORDER)


def test_a_data_owner_pins_all_four_parties(workload):
    binding = WorkloadBinding.for_asset(AssetKind.DATA)

    assert binding.identity_of(workload) == (
        "scripthash::datahash::modelhash::collectorhash"
    )


def test_a_model_owner_pins_only_the_script_and_the_model(workload):
    binding = WorkloadBinding.for_asset(AssetKind.MODEL)

    assert binding.identity_of(workload) == "scripthash::modelhash"
    assert not binding.binds(DATA_TERM)
    assert not binding.binds(COLLECTOR_TERM)


def test_an_asset_kind_knows_its_own_term_and_its_peer():
    assert AssetKind.DATA.own_term == AssetKind.MODEL.peer_term
    assert AssetKind.MODEL.own_term == AssetKind.DATA.peer_term


def test_storage_paths_are_derived_from_the_ids(workload):
    assert workload.results_path == "d2-m3-s1/output"
    assert workload.results_encryption_key_path == "d2-m3-s1/encryption_key"


def test_an_execution_gets_its_own_storage_prefix(workload):
    workload.execution_id = 9

    assert workload.results_path == "d2-m3-s1-e9/output"
