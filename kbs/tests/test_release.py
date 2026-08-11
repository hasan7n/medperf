"""What the broker refuses, mostly.

Tokens here are real: minted by a throwaway attestation authority and verified
by the same code a production broker runs. A fake that answered "valid" would
test nothing, since every path below exists in order to reject something.
"""

import base64
import os

import pytest
from fastapi.testclient import TestClient

from medperf_cc.testing import FakeAttestationAuthority, confidential_space_claims
from medperf_kbs.app import create_app
from medperf_kbs.config import Settings

ASSET_ID = "dataset7"
ADMIN_TOKEN = "the-admin-token"
AUDIENCE = "https://kbs.example.org"
ENCRYPTION_KEY = b"0123456789abcdef0123456789abcdef"

# The identity the fixture token presents, for a policy binding all four terms.
PERMITTED_IDENTITY = "sha256:scripthash::datahash::modelhash::collectorhash"


@pytest.fixture()
def authority():
    return FakeAttestationAuthority()


@pytest.fixture()
def client(tmp_path, authority):
    pki_root = tmp_path / "root.pem"
    pki_root.write_bytes(authority.root_pem)
    settings = Settings(
        storage_root=str(tmp_path / "assets"),
        admin_token=ADMIN_TOKEN,
        pki_root_path=str(pki_root),
    )
    return TestClient(create_app(settings))


def policy_document(identities=None, **attestation):
    return {
        "terms": ["script", "data", "model", "collector"],
        "permitted_identities": [PERMITTED_IDENTITY]
        if identities is None
        else identities,
        "attestation": {"audience": AUDIENCE, **attestation},
    }


def publish(client, policy=None):
    response = client.put(
        f"/v1/assets/{ASSET_ID}",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={
            "key_base64": base64.b64encode(ENCRYPTION_KEY).decode(),
            "policy": policy or policy_document(),
        },
    )
    assert response.status_code == 200


def release(client, authority, nonce=None, claims=None, token_type="PKI", **overrides):
    """Runs the full exchange: challenge, mint a token for it, ask for the key."""
    if nonce is None:
        challenge = client.post(f"/v1/assets/{ASSET_ID}/challenge")
        assert challenge.status_code == 200
        nonce = challenge.json()["nonce"]

    if claims is None:
        claims = confidential_space_claims(eat_nonce=nonce, **overrides)
    token = authority.mint(claims, token_type=token_type)
    return client.post(
        f"/v1/assets/{ASSET_ID}/release",
        json={"attestation_token": token, "nonce": nonce},
    )


# --------------------------------------------------------------------- admin


def test_publishing_needs_the_admin_token(client):
    response = client.put(
        f"/v1/assets/{ASSET_ID}",
        json={"key_base64": "", "policy": policy_document()},
    )

    assert response.status_code == 401


def test_terms_out_of_canonical_order_are_refused(client):
    """The order is what makes two identity strings comparable at all"""
    policy = policy_document()
    policy["terms"] = ["model", "script"]

    response = client.put(
        f"/v1/assets/{ASSET_ID}",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"key_base64": "", "policy": policy},
    )

    assert response.status_code == 422


def test_a_key_is_stored_unreadable_by_anyone_else(client, tmp_path):
    publish(client)

    mode = os.stat(tmp_path / "assets" / ASSET_ID / "key.bin").st_mode

    assert mode & 0o077 == 0


# ------------------------------------------------------------------- release


def test_a_permitted_workload_receives_the_key(client, authority):
    publish(client)

    response = release(client, authority)

    assert response.status_code == 200
    assert base64.b64decode(response.json()["key_base64"]) == ENCRYPTION_KEY
    assert response.json()["identity"] == PERMITTED_IDENTITY


def test_an_unknown_identity_is_refused(client, authority):
    publish(client, policy_document(identities=["something::else"]))

    response = release(client, authority)

    assert response.status_code == 403


def test_a_workload_on_a_different_dataset_is_refused(client, authority):
    """The data hash is part of the identity, so a different one is a
    different workload"""
    publish(client)

    response = release(
        client,
        authority,
        env_override={
            "EXPECTED_DATA_HASH": "someone-elses-data",
            "EXPECTED_MODEL_HASH": "modelhash",
            "EXPECTED_RESULT_COLLECTOR_HASH": "collectorhash",
        },
    )

    assert response.status_code == 403


def test_a_replayed_token_is_refused(client, authority):
    """A Confidential Space token is short lived but not single use, so the
    challenge is what stops an observed one being used again"""
    publish(client)
    challenge = client.post(f"/v1/assets/{ASSET_ID}/challenge").json()
    claims = confidential_space_claims(eat_nonce=challenge["nonce"])
    token = authority.mint(claims)

    body = {"attestation_token": token, "nonce": challenge["nonce"]}
    first = client.post(f"/v1/assets/{ASSET_ID}/release", json=body)
    second = client.post(f"/v1/assets/{ASSET_ID}/release", json=body)

    assert first.status_code == 200
    assert second.status_code == 403


def test_a_token_carrying_the_wrong_nonce_is_refused(client, authority):
    publish(client)
    challenge = client.post(f"/v1/assets/{ASSET_ID}/challenge").json()
    token = authority.mint(confidential_space_claims(eat_nonce="a-different-nonce"))

    response = client.post(
        f"/v1/assets/{ASSET_ID}/release",
        json={"attestation_token": token, "nonce": challenge["nonce"]},
    )

    assert response.status_code == 403


def test_a_token_from_another_authority_is_refused(client):
    """Anchored on the pinned root, never on what the token supplied"""
    publish(client)
    impostor = FakeAttestationAuthority()

    response = release(client, impostor)

    assert response.status_code == 403


def test_a_token_signed_by_the_wrong_key_is_refused(client, authority):
    publish(client)
    challenge = client.post(f"/v1/assets/{ASSET_ID}/challenge").json()
    other = FakeAttestationAuthority()
    token = authority.mint(
        confidential_space_claims(eat_nonce=challenge["nonce"]),
        signing_key=other.leaf_key,
    )

    response = client.post(
        f"/v1/assets/{ASSET_ID}/release",
        json={"attestation_token": token, "nonce": challenge["nonce"]},
    )

    assert response.status_code == 403


def test_a_token_for_another_audience_is_refused(client, authority):
    publish(client)

    response = release(client, authority, aud="https://somewhere.else")

    assert response.status_code == 403


def test_a_workload_outside_confidential_space_is_refused(client, authority):
    publish(client)

    response = release(client, authority, swname="GCE")

    assert response.status_code == 403


def test_a_debuggable_workload_is_refused(client, authority):
    publish(client)

    response = release(client, authority, dbgstat="enabled")

    assert response.status_code == 403


def test_the_wrong_zone_is_refused(client, authority):
    publish(client, policy_document(zone="europe-west4-a"))

    response = release(client, authority)

    assert response.status_code == 403


def test_the_wrong_hardware_is_refused(client, authority):
    publish(client, policy_document(hardware_model="INTEL_TDX"))

    response = release(client, authority)

    assert response.status_code == 403


def test_an_oidc_token_is_refused_when_the_policy_wants_pki(client, authority):
    publish(client)

    response = release(client, authority, token_type="OIDC")

    assert response.status_code == 403


def test_every_refusal_says_the_same_thing(client, authority):
    """A caller who learns *why* it was refused can map the policy by probing"""
    publish(client)

    reasons = {
        release(client, authority, aud="https://elsewhere").json()["detail"],
        release(client, authority, swname="GCE").json()["detail"],
        release(client, FakeAttestationAuthority()).json()["detail"],
    }

    assert len(reasons) == 1


def test_an_unknown_asset_is_not_confused_with_a_refusal(client):
    response = client.post("/v1/assets/no-such-asset/challenge")

    assert response.status_code == 404


# ---------------------------------------------------------------------- blob


def test_the_asset_needs_a_download_grant(client, authority):
    publish(client)
    client.put(
        f"/v1/assets/{ASSET_ID}/blob",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        content=b"ciphertext",
    )

    refused = client.get(
        f"/v1/assets/{ASSET_ID}/blob", params={"download_token": "made-up"}
    )
    granted = release(client, authority).json()["download_token"]
    allowed = client.get(
        f"/v1/assets/{ASSET_ID}/blob", params={"download_token": granted}
    )

    assert refused.status_code == 403
    assert allowed.status_code == 200
    assert allowed.content == b"ciphertext"


def test_a_grant_is_good_for_the_asset_it_was_issued_for(client, authority):
    publish(client)
    granted = release(client, authority).json()["download_token"]

    response = client.get(
        "/v1/assets/another-asset/blob", params={"download_token": granted}
    )

    assert response.status_code == 403


# -------------------------------------------------------------------- policy


def test_a_sync_that_leaves_an_identity_out_takes_it_away(client, authority):
    """The whole of how revocation works"""
    publish(client)
    assert release(client, authority).status_code == 200

    client.put(
        f"/v1/assets/{ASSET_ID}/policy",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"policy": policy_document(identities=[])},
    )

    assert release(client, authority).status_code == 403


def test_a_narrower_binding_matches_more_workloads(client, authority):
    """A policy binding only the script and the model is the same grant
    whichever dataset the workload is pointed at"""
    policy = policy_document(identities=["sha256:scripthash::modelhash"])
    policy["terms"] = ["script", "model"]
    publish(client, policy)

    response = release(
        client,
        authority,
        env_override={
            "EXPECTED_DATA_HASH": "any-dataset-at-all",
            "EXPECTED_MODEL_HASH": "modelhash",
            "EXPECTED_RESULT_COLLECTOR_HASH": "anyone",
        },
    )

    assert response.status_code == 200
