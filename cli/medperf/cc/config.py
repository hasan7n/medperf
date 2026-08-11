"""Reading an entity's confidential computing configuration.

The one place that turns what MedPerf stores on a dataset, a model or a user
into the components that act on it.
"""

from medperf.entities.user import User
from medperf.exceptions import InvalidArgumentError
from medperf_cc.gcp.config import GCPAssetConfig, GCPOperatorConfig
from medperf_cc.gcp.operator import ConfidentialSpaceRunner
from medperf_cc.gcp.vault import GCPVault
from medperf_cc.identity import AssetKind
from medperf_cc.operator import WorkloadRunner
from medperf_cc.policy import AssetPolicy, Party
from medperf_cc.vault import AssetVault

# Every confidential execution encrypts its results for the data owner, so no
# other party's key can appear in an attestation. Naming one would be a policy
# that could never be satisfied, which is worse than not offering it.
SUPPORTED_RESULT_COLLECTORS = [Party.DATA_OWNER]


def validate_cc_config(cc_config: dict, asset_name_prefix: str):
    if cc_config == {}:
        return

    # Derived rather than asked for, so two assets cannot collide in a bucket.
    cc_config["encrypted_asset_bucket_file"] = asset_name_prefix + ".enc"
    cc_config["encrypted_key_bucket_file"] = asset_name_prefix + "_key.enc"

    GCPAssetConfig(**cc_config)


def validate_cc_operator_config(cc_config: dict):
    if cc_config == {}:
        return
    GCPOperatorConfig(**cc_config)


def validate_cc_policy(cc_policy: dict):
    policy = AssetPolicy(**(cc_policy or {}))

    unsupported = [
        party.value
        for party in (policy.allowed_result_collectors or [])
        if party not in SUPPORTED_RESULT_COLLECTORS
    ]
    if unsupported:
        raise InvalidArgumentError(
            "Results can currently only be released to the data owner,"
            f" not to: {', '.join(unsupported)}."
        )


def policy_of(entity) -> AssetPolicy:
    return AssetPolicy(**(entity.get_cc_policy() or {}))


def vault_for(entity, kind: AssetKind) -> AssetVault:
    return GCPVault(entity.get_cc_config(), kind, policy_of(entity))


def runner_for(user: User) -> WorkloadRunner:
    return ConfidentialSpaceRunner(user.get_cc_config())
