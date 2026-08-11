import pytest

from medperf_cc.errors import ConfigurationError
from medperf_cc.identity import AssetKind, WorkloadBinding
from medperf_cc.policy import AssetPolicy
from medperf_cc.testing import confidential_space_claims
from medperf_cc.vault.kbs import KBSVault
from medperf_cc.vault.registry import (
    GCP_KMS_BACKEND,
    KBS_BACKEND,
    backend_of,
    get_vault,
)

KBS_CONFIG = {
    "backend": "kbs",
    "url": "https://kbs.hospital.example:8200/",
    "asset_id": "dataset7",
    "audience": "https://kbs.hospital.example",
    "admin_token": "the-admin-token",
}


def test_a_configuration_naming_no_backend_is_a_google_cloud_one():
    """Nothing written before there was a choice has to be rewritten"""
    assert backend_of({}) == GCP_KMS_BACKEND
    assert backend_of({"project_id": "p"}) == GCP_KMS_BACKEND


def test_an_unknown_backend_is_refused_rather_than_defaulted():
    with pytest.raises(ConfigurationError, match="Unknown key release backend"):
        backend_of({"backend": "something-else"})


def test_the_backend_field_selects_the_vault():
    vault = get_vault(KBS_CONFIG, AssetKind.DATA, AssetPolicy())

    assert isinstance(vault, KBSVault)
    assert vault.backend == KBS_BACKEND


def test_the_admin_token_never_travels_to_the_workload():
    """The workload configuration reaches the VM as environment the operator
    can read, so a broker credential in it would be handed to the operator"""
    vault = get_vault(KBS_CONFIG, AssetKind.DATA, AssetPolicy())

    assert "admin_token" not in vault.workload_config()


def test_the_workload_is_told_which_backend_to_use():
    vault = get_vault(KBS_CONFIG, AssetKind.DATA, AssetPolicy())

    assert vault.workload_config()["backend"] == KBS_BACKEND


def test_an_identity_reads_the_same_from_a_policy_and_from_a_token():
    """One backend has the cloud rebuild the identity out of assertions, the
    other reads the claims itself. They must produce the same string"""
    binding = WorkloadBinding(terms=["script", "data", "model", "collector"])
    claims = confidential_space_claims()["submods"]

    identity = binding.identity_from_claims({"submods": claims})

    assert identity == "sha256:scripthash::datahash::modelhash::collectorhash"


def test_a_claim_the_token_does_not_carry_reads_as_empty():
    binding = WorkloadBinding(terms=["script", "data"])

    assert binding.identity_from_claims({}) == "::"
