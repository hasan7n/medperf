"""An asset its owner has put beyond their own reach.

The ciphertext, the key that opens it, and which workloads may have both. This
is the whole of what a caller needs: it hands over the configuration the asset
carries and gets back something that knows how to publish and authorize, without
ever naming a provider.
"""

import secrets
from typing import List

from medperf_cc.backends import describe, service_config
from medperf_cc.identity import AssetKind, WorkloadIdentity
from medperf_cc.policy import AssetPolicy
from medperf_cc.storage import STORAGES, get_storage
from medperf_cc.vault import VAULTS, get_vault

ENCRYPTION_KEY_BYTES = 32


def asset_backends() -> dict:
    """What an asset owner may choose for each service, and what each choice
    needs from them."""
    return {"storage": describe(STORAGES), "vault": describe(VAULTS)}


def generate_encryption_key() -> bytes:
    return secrets.token_bytes(ENCRYPTION_KEY_BYTES)


class ConfidentialAsset:
    def __init__(
        self, config: dict, asset_name: str, kind: AssetKind, policy: AssetPolicy
    ):
        self.asset_name = asset_name
        self.kind = kind
        self.policy = policy
        self.binding = policy.binding(kind)
        self.storage = get_storage(service_config(config, "storage"), asset_name)
        self.vault = get_vault(
            service_config(config, "vault"), asset_name, self.binding, policy
        )

    def verify(self) -> None:
        """Fails unless the owner can administer everything this asset needs."""
        self.storage.verify()
        self.vault.verify()

    def publish(self, encryption_key: bytes, encrypted_asset_file) -> None:
        """Puts an already-encrypted asset where a workload can reach it.

        The key goes first: a backend holding both halves has nothing to attach
        the ciphertext to until it knows about the asset at all."""
        self.vault.publish_key(encryption_key)
        self.storage.publish(encrypted_asset_file)

    def set_permitted(self, workloads: List[WorkloadIdentity]) -> None:
        """Replaces the set of workloads allowed to open this asset.

        Whatever this owner does not bind collapses here: the same identity is
        reachable through more than one association -- two benchmarks sharing a
        benchmark script, for instance -- and each duplicate would otherwise
        become a redundant entry in a backend's policy.

        Both halves are told, because reading the ciphertext and holding the key
        are two grants, even where one provider happens to give both."""
        identities = list(
            dict.fromkeys(
                self.binding.identity_of(workload) for workload in workloads
            )
        )
        self.storage.permit(identities)
        self.vault.permit(identities)

    def workload_config(self) -> dict:
        """What the workload is told, so it can fetch and open this asset.

        Travels to the confidential VM as environment the operator can read, so
        each backend states what its workload may know rather than handing over
        whatever the owner configured."""
        return {
            "storage": self.storage.workload_config(),
            "vault": self.vault.workload_config(),
        }
