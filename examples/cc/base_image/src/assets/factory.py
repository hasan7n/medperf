"""Choosing where an asset's key and bytes come from.

Each asset's configuration names its own backend, so one run can mix them: a
data owner on an on-prem key broker and a model owner on Google KMS. A
configuration written before backends existed names none, and is a Google
Cloud one.
"""

from .gcp.key import GCPKey
from .gcp.result import GCPResult
from .gcp.storage import GCPStorage
from .kbs.client import KBSKey, KBSStorage

GCP_KMS_BACKEND = "gcp_kms"
KBS_BACKEND = "kbs"

KEY_MANAGERS = {GCP_KMS_BACKEND: GCPKey, KBS_BACKEND: KBSKey}
STORAGE_MANAGERS = {GCP_KMS_BACKEND: GCPStorage, KBS_BACKEND: KBSStorage}


def __backend_of(asset_config: dict) -> str:
    backend = asset_config.get("backend", GCP_KMS_BACKEND)
    if backend not in KEY_MANAGERS:
        supported = ", ".join(sorted(KEY_MANAGERS))
        raise ValueError(
            f"Unsupported key release backend {backend!r}."
            f" This benchmark script supports: {supported}"
        )
    return backend


def storage_manager(asset_config: dict):
    return STORAGE_MANAGERS[__backend_of(asset_config)](asset_config)


def key_manager(asset_config: dict):
    return KEY_MANAGERS[__backend_of(asset_config)](asset_config)


def result_manager(result_config: dict) -> GCPResult:
    # Results always go to the operator's own bucket, which is Google Cloud
    # storage whichever backend the inputs came from.
    return GCPResult(result_config)
