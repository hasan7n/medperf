"""Verification of Confidential Space attestation tokens."""

from medperf_cc.attestation.token import (
    GOOGLE_ISSUER,
    GOOGLE_PKI_ROOT_URL,
    AttestationToken,
    TokenType,
)
from medperf_cc.attestation.issuer import fetch_google_pki_root
from medperf_cc.attestation.verifier import (
    AttestationRequirements,
    TrustAnchor,
    verify_token,
)

__all__ = [
    "GOOGLE_ISSUER",
    "GOOGLE_PKI_ROOT_URL",
    "AttestationRequirements",
    "AttestationToken",
    "TokenType",
    "TrustAnchor",
    "fetch_google_pki_root",
    "verify_token",
]
