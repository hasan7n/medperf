"""Reading an entity's confidential computing configuration.

The one place that turns what MedPerf stores on a dataset, a model or a user
into the components that act on it.
"""

from medperf.entities.user import User
from medperf.exceptions import InvalidArgumentError
from medperf_cc.errors import CCError
from medperf_cc.gcp.config import GCPAssetConfig, GCPOperatorConfig
from medperf_cc.gcp.operator import ConfidentialSpaceRunner
from medperf_cc.identity import AssetKind
from medperf_cc.operator import WorkloadRunner
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault import AssetVault
from medperf_cc.vault.kbs import KBSConfig
from medperf_cc.vault.registry import GCP_KMS_BACKEND, backend_of, get_vault


def validate_cc_config(cc_config: dict, asset_name_prefix: str):
    """Validates an asset's configuration, and fills in what MedPerf decides.

    An asset's name in its backend is derived rather than asked for, so two
    assets cannot collide in the same bucket or broker."""
    if cc_config == {}:
        return

    try:
        backend = backend_of(cc_config)
    except CCError as e:
        raise InvalidArgumentError(str(e))

    if backend == GCP_KMS_BACKEND:
        cc_config["encrypted_asset_bucket_file"] = asset_name_prefix + ".enc"
        cc_config["encrypted_key_bucket_file"] = asset_name_prefix + "_key.enc"
        settings_model = GCPAssetConfig
    else:
        cc_config.setdefault("asset_id", asset_name_prefix)
        settings_model = KBSConfig

    settings = {key: value for key, value in cc_config.items() if key != "backend"}
    settings_model(**settings)


def validate_cc_operator_config(cc_config: dict):
    if cc_config == {}:
        return
    GCPOperatorConfig(**cc_config)


def validate_cc_policy(cc_policy: dict):
    AssetPolicy(**(cc_policy or {}))


def policy_of(entity) -> AssetPolicy:
    return AssetPolicy(**(entity.get_cc_policy() or {}))


def vault_for(entity, kind: AssetKind) -> AssetVault:
    return get_vault(entity.get_cc_config(), kind, policy_of(entity))


def runner_for(user: User) -> WorkloadRunner:
    return ConfidentialSpaceRunner(user.get_cc_config())
