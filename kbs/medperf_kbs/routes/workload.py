"""The workload's side of the broker: attest, then receive.

    POST /v1/assets/{id}/challenge  -> a single-use nonce
    POST /v1/assets/{id}/release    -> the key, if the attestation satisfies the policy
    GET  /v1/assets/{id}/blob       -> the encrypted asset

Every refusal is a bare 403 carrying the same message. The reason goes to the
log, for the asset owner: a caller who learns *why* it was refused can map the
policy one probe at a time.
"""

import base64
import logging
import secrets
import time
from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from medperf_cc.attestation import AttestationToken, TrustAnchor
from medperf_cc.errors import AttestationError
from medperf_kbs.challenges import ChallengeStore
from medperf_kbs.config import Settings
from medperf_kbs.store import AssetNotFound, AssetStore

logger = logging.getLogger("medperf_kbs")

# Long enough to stream a large asset, short enough that a leaked grant is not
# a lasting one.
DOWNLOAD_TOKEN_TTL_SECONDS = 900

REFUSAL = "Attestation refused"


class ReleaseRequest(BaseModel):
    attestation_token: str
    nonce: str


# A registry of small handlers, not one complex function.
def build_router(  # noqa: C901
    settings: Settings,
    store: AssetStore,
    challenges: ChallengeStore,
    anchor: TrustAnchor,
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["workload"])

    # Short lived grants handed out after a successful attestation, so the blob
    # can be fetched without attesting twice: Confidential Space rate limits
    # token requests, and proving the same thing again buys nothing.
    downloads: Dict[str, tuple] = {}

    @router.post("/assets/{asset_id}/challenge")
    def issue_challenge(asset_id: str):
        if not store.exists(asset_id):
            raise HTTPException(status_code=404, detail="Unknown asset")
        challenge = challenges.issue(asset_id)
        return {
            "nonce": challenge.nonce,
            # Stated by the broker, so a workload cannot present a token that
            # was minted for somebody else's audience.
            "audience": store.get_policy(asset_id).attestation.audience,
            "expires_in": settings.challenge_ttl_seconds,
        }

    @router.post("/assets/{asset_id}/release")
    def release(asset_id: str, body: ReleaseRequest):
        try:
            policy = store.get_policy(asset_id)
        except AssetNotFound:
            raise HTTPException(status_code=404, detail="Unknown asset")

        if not challenges.consume(body.nonce, asset_id):
            # Also the path a replayed token takes: its nonce is already burnt.
            raise HTTPException(status_code=403, detail=REFUSAL)

        try:
            token = AttestationToken.parse(body.attestation_token)
            identity = policy.authorize(token, anchor, body.nonce)
        except AttestationError as e:
            logger.warning("refused release of %s: %s", asset_id, e)
            raise HTTPException(status_code=403, detail=REFUSAL)

        logger.info("released key for %s to %s", asset_id, identity)
        download_token = secrets.token_urlsafe(32)
        downloads[download_token] = (
            asset_id,
            time.time() + DOWNLOAD_TOKEN_TTL_SECONDS,
        )
        return {
            "key_base64": base64.b64encode(store.get_key(asset_id)).decode(),
            "download_token": download_token,
            "identity": identity,
        }

    @router.get("/assets/{asset_id}/blob")
    def get_blob(asset_id: str, download_token: str):
        entry = downloads.get(download_token)
        if not entry or entry[0] != asset_id or entry[1] < time.time():
            raise HTTPException(status_code=403, detail="Invalid download token")
        path = store.blob_path(asset_id)
        if path is None:
            raise HTTPException(status_code=404, detail="No stored asset")
        return FileResponse(path, media_type="application/octet-stream")

    return router
