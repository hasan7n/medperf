"""Choosing an asset's vault from its configuration.

The backend is per asset, so a broker-backed dataset and a KMS-backed model can
take part in the same execution -- as long as the benchmark script supports both.

Separate from `medperf_cc.vault` so that importing the base class does not drag
in every implementation of it, which would also make the two import each other.
"""

from medperf_cc.errors import ConfigurationError
from medperf_cc.gcp.vault import GCP_KMS_BACKEND, GCPVault
from medperf_cc.identity import AssetKind
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault.base import AssetVault
from medperf_cc.vault.kbs import KBS_BACKEND, KBSVault

VAULTS = {GCP_KMS_BACKEND: GCPVault, KBS_BACKEND: KBSVault}

# A configuration written before there was a choice is a Google Cloud one.
DEFAULT_BACKEND = GCP_KMS_BACKEND


def backend_of(config: dict) -> str:
    """The backend a configuration names. An unknown one is refused rather than
    quietly treated as the default."""
    backend = (config or {}).get("backend") or DEFAULT_BACKEND
    if backend not in VAULTS:
        supported = ", ".join(sorted(VAULTS))
        raise ConfigurationError(
            f"Unknown key release backend {backend!r}. Supported: {supported}"
        )
    return backend


def backend_settings(config: dict) -> dict:
    """The configuration a backend receives, without the name that chose it."""
    return {key: value for key, value in (config or {}).items() if key != "backend"}


def get_vault(config: dict, kind: AssetKind, policy: AssetPolicy) -> AssetVault:
    backend = backend_of(config)
    return VAULTS[backend](backend_settings(config), kind, policy)
