"""Who may have the key that opens an asset."""

from medperf_cc.backends import backend_of, settings_of
from medperf_cc.backends.medperf_kbs import MEDPERF_KBS
from medperf_cc.backends.mock import MOCK
from medperf_cc.identity import WorkloadScope
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault.base import AssetVault
from medperf_cc.vault.gcp import GCP_VAULT, GCPVault
from medperf_cc.vault.medperf_kbs import KBSVault
from medperf_cc.vault.mock import MockVault

VAULTS = {
    GCP_VAULT: GCPVault,
    MEDPERF_KBS: KBSVault,
    MOCK: MockVault,
}


def get_vault(
    config: dict, asset_name: str, scope: WorkloadScope, policy: AssetPolicy
) -> AssetVault:
    backend = backend_of(config, VAULTS, "vault")
    return VAULTS[backend](settings_of(config), asset_name, scope, policy)


__all__ = ["VAULTS", "AssetVault", "get_vault"]
