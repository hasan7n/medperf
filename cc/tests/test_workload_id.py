import pytest

from medperf_cc.gcp import CCWorkloadID


@pytest.fixture()
def workload():
    return CCWorkloadID(
        script_hash="scripthash",
        data_hash="datahash",
        model_hash="modelhash",
        result_collector_hash="collectorhash",
        script_id=1,
        data_id=2,
        model_id=3,
    )


def test_a_data_owner_binds_all_four_parties(workload):
    assert workload.id == "scripthash::datahash::modelhash::collectorhash"


def test_a_model_owner_binds_only_the_script_and_the_model(workload):
    assert workload.id_for_model == "scripthash::modelhash"


def test_a_model_side_workload_carries_only_what_it_binds():
    workload = CCWorkloadID.for_model_policy(
        model_hash="modelhash", script_hash="scripthash", model_id=3, script_id=1
    )

    assert workload.id_for_model == "scripthash::modelhash"
    assert workload.data_hash == ""
    assert workload.result_collector_hash == ""


def test_storage_paths_are_derived_from_the_ids(workload):
    assert workload.results_path == "d2-m3-s1/output"
    assert workload.results_encryption_key_path == "d2-m3-s1/encryption_key"


def test_an_execution_gets_its_own_storage_prefix(workload):
    workload.execution_id = 9

    assert workload.results_path == "d2-m3-s1-e9/output"
