"""The MedPerf on-prem key broker.

An asset owner runs this instead of handing their key to a cloud KMS. It holds
the encryption key and the encrypted asset, and releases them only to a workload
that proves, by attestation, that it is the exact script the owner authorized,
running on the inputs they authorized, in a genuine confidential VM.

What it changes: the key never reaches a cloud provider, so nobody but the asset
owner can decrypt the asset at rest. What it does not change: the broker still
believes an attestation token signed by Google, or by Intel Trust Authority if
the owner points `MEDPERF_KBS_EXPECTED_ISSUER` there. A workload cannot hand
over raw hardware evidence, because Confidential Space does not expose it, so
trusting *a* verifier is unavoidable. Choosing which one is the control you get.

The policy the broker enforces is the policy MedPerf already writes to Google
Cloud -- `medperf_cc.policy` produces both -- so an asset can move between
backends without its owner restating what they meant.
"""

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from medperf_kbs.challenges import ChallengeStore
from medperf_kbs.config import Settings, load_settings
from medperf_kbs.routes import admin, workload
from medperf_kbs.store import AssetNotFound, AssetStore

logger = logging.getLogger("medperf_kbs")


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or load_settings()
    store = AssetStore(root=settings.storage_root)
    challenges = ChallengeStore(ttl_seconds=settings.challenge_ttl_seconds)
    # Read once at startup: a broker that fetched its own trust anchor on the
    # verification path would not be verifying anything.
    anchor = settings.trust_anchor()

    app = FastAPI(title="MedPerf Key Broker", version="1.0")
    app.include_router(admin.build_router(settings, store))
    app.include_router(workload.build_router(settings, store, challenges, anchor))

    @app.get("/v1/health")
    def health():
        return {"status": "ok", "assets": len(store.list_assets())}

    @app.exception_handler(AssetNotFound)
    def asset_not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Unknown asset"})

    app.state.store = store
    app.state.settings = settings
    app.state.anchor = anchor
    return app
