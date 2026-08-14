"""The services whose word we take that an attestation is genuine.

A caller names one; getting from that name to a trust anchor is this module's
business. Adding Intel Trust Authority later is adding an entry here, with
nothing outside this package to change.

Fetching a root is deliberately not something `verifier` does: a verifier that
fetches its own trust anchor while verifying is not verifying anything. Whoever
needs one asks for it here, once, and hands it over.
"""

from dataclasses import dataclass

import requests

from medperf_cc.attestation.token import (
    GOOGLE_ISSUER,
    GOOGLE_PKI_ROOT_URL,
)
from medperf_cc.attestation.verifier import TrustAnchor
from medperf_cc.errors import AttestationError

GOOGLE = "google"


@dataclass(frozen=True)
class Authority:
    """Who signs an attestation, and where its root certificate comes from."""

    issuer: str
    pki_root_url: str

    def fetch_pki_root(self, timeout: int) -> bytes:
        response = requests.get(self.pki_root_url, timeout=timeout)
        response.raise_for_status()
        return response.content


AUTHORITIES = {
    GOOGLE: Authority(issuer=GOOGLE_ISSUER, pki_root_url=GOOGLE_PKI_ROOT_URL),
}


def trust_anchor(authority: str = GOOGLE, timeout: int = 30) -> TrustAnchor:
    """What to accept as proof that a token this authority signed is genuine.

    Fetched now rather than pinned on disk. Pinning buys offline verification,
    which is worth it for something authenticating live workloads all day -- see
    the key broker -- and not for checking a result, which happens rarely and
    only ever with a network."""
    known = AUTHORITIES.get(authority)
    if known is None:
        raise AttestationError(
            f"Unknown attestation authority {authority!r}."
            f" Supported: {', '.join(sorted(AUTHORITIES))}"
        )

    try:
        return TrustAnchor(
            pki_root_pem=known.fetch_pki_root(timeout), expected_issuer=known.issuer
        )
    except Exception as e:
        raise AttestationError(
            f"Could not fetch the root certificate of {authority}: {e}"
        )
