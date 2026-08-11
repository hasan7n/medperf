"""The asset owner's side of the broker: publishing keys, assets and policies.

Authenticated with a bearer token, and expected to be reachable only from the
owner's own network. MedPerf calls it during `configure_*_for_cc` and
`update_*_cc_policy`.
"""

import base64
import logging
import os
import secrets
import tempfile

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from medperf_kbs.config import Settings
from medperf_kbs.policy import AssetPolicy
from medperf_kbs.store import AssetStore

logger = logging.getLogger("medperf_kbs")


class PutAssetRequest(BaseModel):
    key_base64: str
    policy: AssetPolicy


class PutPolicyRequest(BaseModel):
    policy: AssetPolicy


# A registry of small handlers, not one complex function.
def build_router(settings: Settings, store: AssetStore) -> APIRouter:  # noqa: C901
    router = APIRouter(prefix="/v1", tags=["admin"])

    def require_admin(authorization: str = Header(None)):
        expected = f"Bearer {settings.admin_token}"
        # Constant time, so the token cannot be recovered a byte at a time.
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @router.get("/assets")
    def list_assets(_=Depends(require_admin)):
        return {"assets": store.list_assets()}

    @router.put("/assets/{asset_id}")
    def put_asset(asset_id: str, body: PutAssetRequest, _=Depends(require_admin)):
        """Stores an asset's key and policy, when its owner configures it."""
        store.put_policy(asset_id, body.policy)
        store.put_key(asset_id, base64.b64decode(body.key_base64))
        logger.info("stored key and policy for asset %s", asset_id)
        return {"status": "ok"}

    @router.put("/assets/{asset_id}/policy")
    def put_policy(asset_id: str, body: PutPolicyRequest, _=Depends(require_admin)):
        """Replaces the permitted identities.

        Called on every policy sync, and the whole of how a grant is taken
        away: whatever a sync leaves out stops being able to decrypt."""
        if not store.exists(asset_id):
            raise HTTPException(status_code=404, detail="Unknown asset")
        store.put_policy(asset_id, body.policy)
        logger.info(
            "updated policy for asset %s: %d permitted identities",
            asset_id,
            len(body.policy.permitted_identities),
        )
        return {"status": "ok"}

    @router.put("/assets/{asset_id}/blob")
    async def put_blob(asset_id: str, request: Request, _=Depends(require_admin)):
        """Uploads the encrypted asset. Streamed, since assets can be large."""
        if not store.exists(asset_id):
            raise HTTPException(status_code=404, detail="Unknown asset")
        os.makedirs(settings.storage_root, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=settings.storage_root)
        try:
            with os.fdopen(descriptor, "wb") as f:
                async for chunk in request.stream():
                    f.write(chunk)
            store.put_blob(asset_id, temporary)
        except Exception:
            if os.path.exists(temporary):
                os.remove(temporary)
            raise
        return {"status": "ok"}

    @router.delete("/assets/{asset_id}")
    def delete_asset(asset_id: str, _=Depends(require_admin)):
        store.delete(asset_id)
        return {"status": "ok"}

    return router
