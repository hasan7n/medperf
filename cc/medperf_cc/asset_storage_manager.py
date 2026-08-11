from medperf_cc.errors import ConfigurationError
from medperf_cc.gcp import (
    GCPAssetConfig,
    upload_from_file_object_to_gcs,
)
from medperf_cc.asset_check import verify_asset_owner_setup


class AssetStorageManager:
    """Where an asset's ciphertext lives.

    The asset arrives already encrypted: the key belongs to its owner, and
    there is no reason for it to pass through here."""

    def __init__(self, config: dict):
        self.config = GCPAssetConfig(**config)

    def setup(self):
        success, message = verify_asset_owner_setup(
            self.config.bucket, self.config.full_key_name, self.config.full_wip_name
        )
        if not success:
            raise ConfigurationError(
                f"Asset owner setup verification failed: {message}"
            )

    def store_asset(self, encrypted_asset_file):
        """Uploads an open, readable file holding the encrypted asset."""
        upload_from_file_object_to_gcs(
            self.config,
            encrypted_asset_file,
            self.config.encrypted_asset_bucket_file,
        )
