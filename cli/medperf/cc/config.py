"""Validating the confidential computing configuration an entity carries."""

from medperf_cc.gcp import GCPAssetConfig, GCPOperatorConfig


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
