"""Confidential computing components used by MedPerf.

Nothing here knows what a benchmark, a dataset or a model is, and nothing a
caller writes has to name a provider. A caller translates its own domain into a
workload identity and an asset policy, hands over the configuration an asset or
an operator carries, and these components resolve the rest:

    ConfidentialAsset    an asset's ciphertext, its key, and who may have them
    get_runner           starting a confidential workload and fetching its output

Which backend answers is decided by the configuration alone. See
`medperf_cc.backends` for how it is read.
"""

from medperf_cc.asset import (
    ConfidentialAsset,
    asset_backends,
    generate_encryption_key,
)
from medperf_cc.identity import (
    AssetKind,
    WorkloadGrant,
    WorkloadIdentity,
)
from medperf_cc.policy import AssetPolicy, Party
from medperf_cc.runner import WorkloadRunner, get_runner, runner_backends

__all__ = [
    "AssetKind",
    "AssetPolicy",
    "ConfidentialAsset",
    "Party",
    "WorkloadGrant",
    "WorkloadIdentity",
    "WorkloadRunner",
    "asset_backends",
    "generate_encryption_key",
    "get_runner",
    "runner_backends",
]
