"""Fetching an asset from an on-prem key broker.

The mirror image of the GCP path: instead of federating an attestation token
into Google credentials and asking KMS to unwrap a key, the workload presents
the token to the asset owner's own broker, which verifies it itself and releases
the key directly.

    POST {url}/v1/assets/{id}/challenge  -> a nonce
    (ask the launcher for a token carrying that nonce)
    POST {url}/v1/assets/{id}/release    -> the key
    GET  {url}/v1/assets/{id}/blob       -> the encrypted asset
"""

import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, fields
from typing import Optional

from assets.attestation import request_token

TIMEOUT_SECONDS = 120
CHUNK_SIZE = 1024 * 1024


@dataclass
class KBSAssetConfig:
    url: str
    asset_id: str
    audience: str
    backend: Optional[str] = None
    verify_tls: bool = True
    token_type: str = "PKI"
    issuer: str = "google"

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")


class KBSSession:
    """One attestation exchange, reused for both the key and the asset.

    Confidential Space rate limits token requests and there is no reason to
    prove the same thing twice, so the broker hands back a short lived download
    grant along with the key."""

    def __init__(self, asset_config_dict: dict):
        known = {field.name for field in fields(KBSAssetConfig)}
        self.config = KBSAssetConfig(
            **{
                key: value
                for key, value in asset_config_dict.items()
                if key in known
            }
        )
        self.key_bytes: Optional[bytes] = None
        self.download_token: Optional[str] = None

    def initialize(self) -> None:
        """Attests once. The key and storage managers both call this."""
        if self.key_bytes is not None:
            return

        challenge = self.__post("/challenge", {})
        nonce = challenge["nonce"]
        # The broker states the audience it will accept, so a workload cannot
        # accidentally present a token minted for somebody else.
        audience = challenge.get("audience") or self.config.audience

        token = request_token(
            audience=audience,
            nonces=[nonce],
            token_type=self.config.token_type,
            issuer=self.config.issuer,
        )
        released = self.__post(
            "/release", {"attestation_token": token, "nonce": nonce}
        )
        self.key_bytes = base64.b64decode(released["key_base64"])
        self.download_token = released.get("download_token")

    def get_key(self, output_path: str) -> None:
        if self.key_bytes is None:
            raise RuntimeError("initialize() must run before the key is available")
        with open(output_path, "wb") as f:
            f.write(self.key_bytes)

    def get_asset(self, output_path: str) -> None:
        if not self.download_token:
            raise RuntimeError("initialize() must run before the asset is available")
        query = urllib.parse.urlencode({"download_token": self.download_token})
        request = urllib.request.Request(f"{self.__asset_url()}/blob?{query}")
        with self.__open(request) as response:
            with open(output_path, "wb") as f:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)

    def __asset_url(self) -> str:
        return f"{self.config.base_url}/v1/assets/{self.config.asset_id}"

    def __post(self, path: str, body: dict) -> dict:
        request = urllib.request.Request(
            f"{self.__asset_url()}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.__open(request) as response:
            return json.loads(response.read())

    def __open(self, request):
        context = None
        if not self.config.verify_tls:
            context = ssl._create_unverified_context()
        try:
            return urllib.request.urlopen(
                request, timeout=TIMEOUT_SECONDS, context=context
            )
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise RuntimeError(
                f"Key broker refused {request.full_url} ({e.code}): {detail}"
            )
        except urllib.error.URLError as e:
            raise RuntimeError(f"Cannot reach the key broker: {e}")


# `setup_assets` builds the key manager and the storage manager separately, and
# both would otherwise attest. One session per asset, shared between them.
SESSIONS = {}


def session_for(asset_config_dict: dict) -> KBSSession:
    key = (asset_config_dict.get("url"), asset_config_dict.get("asset_id"))
    if key not in SESSIONS:
        SESSIONS[key] = KBSSession(asset_config_dict)
    return SESSIONS[key]


class KBSKey:
    """The key half of the manager interface `setup_assets` expects."""

    def __init__(self, asset_config_dict: dict):
        self.session = session_for(asset_config_dict)

    def initialize(self) -> None:
        self.session.initialize()

    def get_key(self, output_path: str) -> None:
        self.session.get_key(output_path)


class KBSStorage:
    """The storage half of the same interface."""

    def __init__(self, asset_config_dict: dict):
        self.session = session_for(asset_config_dict)

    def initialize(self) -> None:
        self.session.initialize()

    def get_asset(self, output_path: str) -> None:
        self.session.get_asset(output_path)
