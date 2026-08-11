from typing import List

import pytest

from medperf_cc.identity import AssetKind, WorkloadIdentity
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault import AssetVault


class RecordingVault(AssetVault):
    """A vault that records what it was told to permit, and nothing else."""

    def __init__(self, kind: AssetKind):
        super().__init__({}, kind, AssetPolicy())
        self.permitted = None

    def verify(self):
        pass

    def publish_key(self, encryption_key: bytes):
        pass

    def publish_asset(self, encrypted_asset_file):
        pass

    def set_permitted_identities(self, identities: List[str]):
        self.permitted = identities


def workload(data_hash="datahash", collector_hash="collectorhash"):
    return WorkloadIdentity(
        script_hash="scripthash",
        model_hash="modelhash",
        data_hash=data_hash,
        result_collector_hash=collector_hash,
        script_id=1,
        model_id=2,
        data_id=3,
    )


@pytest.mark.parametrize("kind", [AssetKind.DATA, AssetKind.MODEL])
def test_repeated_identities_collapse(kind):
    """The same identity is reachable through more than one association, and
    each duplicate would become a redundant entry in the backend's policy"""
    vault = RecordingVault(kind)

    vault.set_permitted([workload(), workload(), workload()])

    assert vault.permitted == [vault.binding.identity_of(workload())]


def test_a_model_owner_collapses_what_they_do_not_pin():
    """Two workloads differing only in data and collector are one grant to a
    model owner, who pins neither"""
    vault = RecordingVault(AssetKind.MODEL)

    vault.set_permitted([workload(), workload(data_hash="other", collector_hash="x")])

    assert vault.permitted == ["scripthash::modelhash"]


def test_a_data_owner_keeps_them_apart():
    vault = RecordingVault(AssetKind.DATA)

    vault.set_permitted([workload(), workload(data_hash="other")])

    assert len(vault.permitted) == 2
