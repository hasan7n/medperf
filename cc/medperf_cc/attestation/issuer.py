"""Fetching an attestation issuer's root certificate.

Kept apart from `verifier`, which reaches nothing: a verifier that fetches its
own trust anchor while verifying is not verifying anything. Whoever needs a root
gets it here, deliberately, and hands it to the verifier.

A key broker pins one on disk once, because it authenticates live workloads
constantly. A results auditor fetches one when it checks a proof, which happens
rarely and never offline.
"""

import requests

from medperf_cc.attestation.token import GOOGLE_PKI_ROOT_URL


def fetch_google_pki_root(timeout: int = 30) -> bytes:
    """Downloads Google's attestation PKI root."""
    response = requests.get(GOOGLE_PKI_ROOT_URL, timeout=timeout)
    response.raise_for_status()
    return response.content
