"""Where an asset's ciphertext lives, and who may have the key that opens it.

A vault does transport and authorization, never cryptography: it is handed an
already-encrypted asset and the key that opens it, and its job is to put both
somewhere a workload can reach, and to enforce which workload identities may
ask for the key.
"""

from abc import ABC, abstractmethod
from typing import List

from medperf_cc.identity import AssetKind, WorkloadBinding, WorkloadIdentity
from medperf_cc.policy import AssetPolicy


class AssetVault(ABC):
    def __init__(self, config: dict, kind: AssetKind, policy: AssetPolicy):
        self.config = config
        self.kind = kind
        self.policy = policy
        self.binding = WorkloadBinding.for_asset(kind)

    def set_permitted(self, workloads: List[WorkloadIdentity]) -> None:
        """Replaces the set of workloads allowed to decrypt this asset.

        Whatever this owner does not bind collapses here: the same identity is
        reachable through more than one association -- two benchmarks sharing a
        benchmark script, for instance -- and each duplicate would otherwise
        become a redundant entry in the backend's policy."""
        identities = dict.fromkeys(
            self.binding.identity_of(workload) for workload in workloads
        )
        self.set_permitted_identities(list(identities))

    @abstractmethod
    def verify(self) -> None:
        """Fails unless the owner can administer this vault."""

    @abstractmethod
    def publish_key(self, encryption_key: bytes) -> None:
        """Stores the key, and everything a workload must satisfy to get it."""

    @abstractmethod
    def publish_asset(self, encrypted_asset_file) -> None:
        """Puts the ciphertext, read from an open file, where a workload can
        fetch it."""

    @abstractmethod
    def set_permitted_identities(self, identities: List[str]) -> None:
        """Replaces the workload identity strings allowed to decrypt."""
