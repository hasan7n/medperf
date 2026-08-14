"""Choosing where an asset's bytes, its key, and the results come from.

Each service names its own backend, so one run can mix them: a dataset held
by an on-prem key broker and a model held in cloud storage, with the results
going back to wherever the operator asked for them.

    {"storage": {"backend": ...}, "vault": {"backend": ...}}
"""

from .gcp.result import GCPResult
from .gcp.storage import GCPStorage
from .gcp.vault import GCPVault
from .medperf_kbs.client import KBSStorage, KBSVault
from .mock.backend import MockResult, MockStorage, MockVault

GCP = "gcp"
MEDPERF_KBS = "medperf_kbs"
MOCK = "mock"

STORAGES = {GCP: GCPStorage, MEDPERF_KBS: KBSStorage, MOCK: MockStorage}
VAULTS = {GCP: GCPVault, MEDPERF_KBS: KBSVault, MOCK: MockVault}
RESULTS = {GCP: GCPResult, MOCK: MockResult}


def storage_manager(asset_config: dict):
    return __build(STORAGES, "storage", asset_config.get("storage", {}))


def key_manager(asset_config: dict):
    return __build(VAULTS, "vault", asset_config.get("vault", {}))


def result_manager(result_config: dict):
    return __build(RESULTS, "results", result_config)


def __build(registry: dict, service: str, config: dict):
    backend = config.get("backend")
    if backend not in registry:
        supported = ", ".join(sorted(registry))
        raise ValueError(
            f"Unsupported {service} backend {backend!r}."
            f" This benchmark script supports: {supported}"
        )
    return registry[backend](config)
