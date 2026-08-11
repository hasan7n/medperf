"""An on-prem key broker: the asset owner's own service holds the key.

This is the administrative half -- publishing the key, the asset and the policy.
The workload's half of the exchange, challenge then attest then receive, is
implemented in whatever runs inside the confidential VM.
"""

import base64
from typing import List, Optional

import requests
from pydantic import BaseModel

from medperf_cc.errors import ConfigurationError, OperationError
from medperf_cc.identity import AssetKind
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault.base import AssetVault

KBS_BACKEND = "kbs"


class KBSConfig(BaseModel):
    """`admin_token` is the only secret here, and never leaves this machine."""

    url: str
    asset_id: str
    audience: str
    admin_token: Optional[str] = None
    ca_bundle: Optional[str] = None
    verify_tls: bool = True
    timeout_seconds: int = 60

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")

    def tls_verify(self):
        if not self.verify_tls:
            return False
        return self.ca_bundle or True


class KBSVault(AssetVault):
    def __init__(self, config: dict, kind: AssetKind, policy: AssetPolicy):
        super().__init__(config, kind, policy)
        self.kbs = KBSConfig(**config)

    @property
    def backend(self) -> str:
        return KBS_BACKEND

    def workload_config(self) -> dict:
        """Named field by field rather than filtered, so that a secret added to
        the configuration later cannot travel to the VM by default."""
        return {
            "backend": self.backend,
            "url": self.kbs.base_url,
            "asset_id": self.kbs.asset_id,
            "audience": self.kbs.audience,
            "verify_tls": self.kbs.verify_tls,
        }

    def verify(self) -> None:
        try:
            response = requests.get(
                f"{self.kbs.base_url}/v1/health",
                timeout=self.kbs.timeout_seconds,
                verify=self.kbs.tls_verify(),
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ConfigurationError(f"Cannot reach the key broker: {e}")

        if not self.kbs.admin_token:
            raise ConfigurationError(
                "An admin token is required to publish policy to the key broker"
            )

    def publish_key(self, encryption_key: bytes) -> None:
        self.__put(
            f"/v1/assets/{self.kbs.asset_id}",
            json={
                "key_base64": base64.b64encode(encryption_key).decode(),
                "policy": self.__policy_document([]),
            },
        )

    def publish_asset(self, encrypted_asset_file) -> None:
        self.__put(f"/v1/assets/{self.kbs.asset_id}/blob", data=encrypted_asset_file)

    def set_permitted_identities(self, identities: List[str]) -> None:
        self.__put(
            f"/v1/assets/{self.kbs.asset_id}/policy",
            json={"policy": self.__policy_document(identities)},
        )

    def __policy_document(self, identities: List[str]) -> dict:
        return {
            "terms": self.binding.terms,
            "permitted_identities": identities,
            "attestation": {
                "audience": self.kbs.audience,
                "zone": self.policy.location,
                "hardware_model": self.policy.hardware,
            },
        }

    def __put(self, path: str, **kwargs):
        try:
            response = requests.put(
                f"{self.kbs.base_url}{path}",
                headers={"Authorization": f"Bearer {self.kbs.admin_token}"},
                timeout=self.kbs.timeout_seconds,
                verify=self.kbs.tls_verify(),
                **kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise OperationError(f"Key broker rejected {path}: {e}")
