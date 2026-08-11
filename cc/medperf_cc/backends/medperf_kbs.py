"""Talking to an on-prem MedPerf key broker.

The broker holds both halves of an asset -- its ciphertext and the key that
opens it -- so the storage backend and the vault backend speak to the same
service with the same settings, and share this client.
"""

from typing import Optional

import requests
from pydantic import BaseModel

from medperf_cc.errors import ConfigurationError, OperationError

MEDPERF_KBS = "medperf_kbs"


class KBSConfig(BaseModel):
    """`admin_token` is the only secret here, and never leaves this machine."""

    url: str
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

    class Config:
        extra = "ignore"


class KBSClient:
    """The asset owner's side of the broker: publishing, never releasing."""

    def __init__(self, config: dict, asset_id: str):
        self.config = KBSConfig(**config)
        self.asset_id = asset_id

    @property
    def asset_url(self) -> str:
        return f"{self.config.base_url}/v1/assets/{self.asset_id}"

    def check_reachable(self) -> None:
        try:
            response = requests.get(
                f"{self.config.base_url}/v1/health",
                timeout=self.config.timeout_seconds,
                verify=self.config.tls_verify(),
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ConfigurationError(f"Cannot reach the key broker: {e}")

        if not self.config.admin_token:
            raise ConfigurationError(
                "An admin token is required to publish to the key broker"
            )

    def put(self, path: str = "", **kwargs):
        try:
            response = requests.put(
                f"{self.asset_url}{path}",
                headers={"Authorization": f"Bearer {self.config.admin_token}"},
                timeout=self.config.timeout_seconds,
                verify=self.config.tls_verify(),
                **kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise OperationError(f"Key broker rejected {self.asset_url}{path}: {e}")

    def workload_config(self, backend: str) -> dict:
        """Named field by field rather than filtered, so a secret added to the
        configuration later cannot travel to the VM by default."""
        return {
            "backend": backend,
            "url": self.config.base_url,
            "asset_id": self.asset_id,
            "audience": self.config.audience,
            "verify_tls": self.config.verify_tls,
        }
