"""Key release by an on-prem broker the asset owner runs themselves.

The administrative half only. The workload's half of the exchange -- challenge,
attest, receive -- is implemented in whatever runs inside the confidential VM.

What this changes: the key never reaches a cloud provider. What it does not: the
broker still believes an attestation token signed by somebody. Choosing who is
the control it gives you.
"""

import base64
from typing import List

from medperf_cc.backends.medperf_kbs import MEDPERF_KBS, KBSClient, KBSConfig
from medperf_cc.identity import WorkloadScope
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault.base import AssetVault


class KBSVault(AssetVault):
    SETTINGS = KBSConfig

    def __init__(
        self,
        config: dict,
        asset_name: str,
        scope: WorkloadScope,
        policy: AssetPolicy,
    ):
        super().__init__(config, asset_name, scope, policy)
        self.broker = KBSClient(config, asset_name)

    @property
    def backend(self) -> str:
        return MEDPERF_KBS

    def verify(self) -> None:
        self.broker.check_reachable()

    def publish_key(self, encryption_key: bytes) -> None:
        self.broker.put(
            json={
                "key_base64": base64.b64encode(encryption_key).decode(),
                "policy": self.__policy_document([]),
            }
        )

    def permit(self, identities: List[str]) -> None:
        self.broker.put("/policy", json={"policy": self.__policy_document(identities)})

    def workload_config(self) -> dict:
        return self.broker.workload_config(self.backend)

    def __policy_document(self, identities: List[str]) -> dict:
        return {
            "terms": self.scope.terms,
            "permitted_identities": identities,
            "attestation": {
                "audience": self.broker.config.audience,
                "zone": self.policy.location,
                "hardware_model": self.policy.hardware,
            },
        }
