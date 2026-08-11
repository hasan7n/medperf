"""An asset's ciphertext held by the same broker that holds its key.

Nothing to authorize separately: the broker hands out a short lived download
grant as part of releasing the key, so a workload that satisfied the vault's
policy is the only one that can fetch the bytes.
"""

from typing import List

from medperf_cc.backends.medperf_kbs import MEDPERF_KBS, KBSClient, KBSConfig
from medperf_cc.storage.base import AssetStorage


class KBSStorage(AssetStorage):
    SETTINGS = KBSConfig

    def __init__(self, config: dict, asset_name: str):
        super().__init__(config, asset_name)
        self.broker = KBSClient(config, asset_name)

    @property
    def backend(self) -> str:
        return MEDPERF_KBS

    def verify(self) -> None:
        self.broker.check_reachable()

    def publish(self, encrypted_asset_file) -> None:
        self.broker.put("/blob", data=encrypted_asset_file)

    def permit(self, identities: List[str]) -> None:
        """Nothing to do: the vault's release is what grants the download."""

    def workload_config(self) -> dict:
        return self.broker.workload_config(self.backend)
