"""Broker settings, read from the environment."""

import json
import os
from dataclasses import dataclass
from typing import Optional

from medperf_cc.attestation import GOOGLE_ISSUER, TrustAnchor


@dataclass
class Settings:
    storage_root: str
    admin_token: str
    # The trust anchor is pinned on disk, once, by whoever runs the broker. A
    # broker that downloaded its own root at startup would be trusting the
    # network it is there to defend against.
    pki_root_path: Optional[str] = None
    jwks_path: Optional[str] = None
    expected_issuer: str = GOOGLE_ISSUER
    challenge_ttl_seconds: int = 300

    def trust_anchor(self) -> TrustAnchor:
        if not self.pki_root_path and not self.jwks_path:
            raise RuntimeError(
                "No trust anchor configured. Set MEDPERF_KBS_PKI_ROOT to a pinned"
                " attestation PKI root certificate (preferred), or"
                " MEDPERF_KBS_JWKS to a JWKS file."
            )

        anchor = TrustAnchor(expected_issuer=self.expected_issuer)
        if self.pki_root_path:
            with open(self.pki_root_path, "rb") as f:
                anchor.pki_root_pem = f.read()
        if self.jwks_path:
            with open(self.jwks_path) as f:
                anchor.jwks = json.load(f)
        return anchor


def load_settings() -> Settings:
    admin_token = os.getenv("MEDPERF_KBS_ADMIN_TOKEN")
    if not admin_token:
        raise RuntimeError("MEDPERF_KBS_ADMIN_TOKEN must be set")

    return Settings(
        storage_root=os.getenv("MEDPERF_KBS_STORAGE", "/var/lib/medperf-kbs"),
        admin_token=admin_token,
        pki_root_path=os.getenv("MEDPERF_KBS_PKI_ROOT"),
        jwks_path=os.getenv("MEDPERF_KBS_JWKS"),
        expected_issuer=os.getenv("MEDPERF_KBS_EXPECTED_ISSUER", GOOGLE_ISSUER),
        challenge_ttl_seconds=int(os.getenv("MEDPERF_KBS_CHALLENGE_TTL", "300")),
    )
