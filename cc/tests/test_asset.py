"""An asset's whole lifecycle, on the backend that needs no cloud account.

The mock backends exist so this can run anywhere, and so that the abstraction
has a second implementation keeping it honest: anything these tests reach for
that only Google Cloud could provide is a leak.
"""

import io
import json
import os

import pytest

from medperf_cc import AssetKind, AssetPolicy, ConfidentialAsset, Party
from medperf_cc.backends.mock import MOCK, PERMITTED_FILE
from medperf_cc.identity import WorkloadIdentity
from medperf_cc.storage.mock import ASSET_FILE
from medperf_cc.vault.mock import KEY_FILE

CIPHERTEXT = b"not really encrypted, but the vault never looks"
KEY = b"0123456789abcdef0123456789abcdef"


@pytest.fixture()
def config(tmp_path):
    return {"backend": MOCK, "root": str(tmp_path / "cc")}


def workload(data_hash="datahash", collector_hash="collectorhash"):
    return WorkloadIdentity(
        script_hash="scripthash",
        model_hash="modelhash",
        data_hash=data_hash,
        result_collector_hash=collector_hash,
        script_id=1,
        model_id=2,
        data_id=3,
    )


def published(config, kind=AssetKind.DATA, policy=None):
    asset = ConfidentialAsset(config, "dataset3", kind, policy or AssetPolicy())
    asset.verify()
    asset.publish_key(KEY)
    asset.publish(io.BytesIO(CIPHERTEXT))
    return asset


def test_the_key_and_the_ciphertext_are_published_apart(config):
    asset = published(config)

    assert asset.storage.store.read(ASSET_FILE) == CIPHERTEXT
    assert asset.vault.store.read(KEY_FILE) == KEY


def test_both_halves_are_told_who_may_open_the_asset(config):
    """Reading the ciphertext and holding the key are two grants, even where
    one provider happens to give both"""
    asset = published(config)

    asset.set_permitted([workload()])

    assert asset.storage.store.permitted() == asset.vault.store.permitted()
    assert asset.storage.store.permitted() == [asset.binding.identity_of(workload())]


def test_repeated_identities_collapse(config):
    asset = published(config)

    asset.set_permitted([workload(), workload(), workload()])

    assert len(asset.vault.store.permitted()) == 1


def test_a_model_owner_collapses_what_they_do_not_pin(config):
    """Two workloads differing only in data are one grant to a model owner"""
    asset = ConfidentialAsset(config, "model4", AssetKind.MODEL, AssetPolicy())

    asset.set_permitted([workload(), workload(data_hash="other")])

    assert asset.vault.store.permitted() == ["scripthash::modelhash"]


def test_a_data_owner_keeps_them_apart(config):
    asset = ConfidentialAsset(config, "dataset3", AssetKind.DATA, AssetPolicy())

    asset.set_permitted([workload(), workload(data_hash="other")])

    assert len(asset.vault.store.permitted()) == 2


def test_a_sync_that_leaves_an_identity_out_takes_it_away(config):
    """The whole of how a grant is revoked"""
    asset = published(config)
    asset.set_permitted([workload()])

    asset.set_permitted([])

    assert asset.vault.store.permitted() == []


def test_the_workload_is_told_where_both_halves_are(config):
    asset = published(config)

    told = asset.workload_config()

    assert told["storage"]["backend"] == MOCK
    assert told["vault"]["backend"] == MOCK
    assert told["storage"]["asset_name"] == "dataset3"


def test_a_mixed_configuration_tells_the_workload_about_both(tmp_path):
    """A dataset can live in one provider and have its key released by another,
    and the workload has to be able to reach each of them"""
    config = {
        "backend": MOCK,
        "root": str(tmp_path / "cc"),
        "vault": {
            "backend": "medperf_kbs",
            "url": "https://kbs.example/",
            "audience": "https://kbs.example",
            "admin_token": "secret",
        },
    }

    told = ConfidentialAsset(
        config, "dataset3", AssetKind.DATA, AssetPolicy()
    ).workload_config()

    assert told["storage"]["backend"] == MOCK
    assert told["vault"]["backend"] == "medperf_kbs"


def test_no_secret_reaches_the_workload(tmp_path):
    """What the workload is told travels to the VM as environment the operator
    can read"""
    config = {
        "backend": "medperf_kbs",
        "url": "https://kbs.example",
        "audience": "https://kbs.example",
        "admin_token": "the-admin-token",
    }

    told = ConfidentialAsset(config, "dataset3", AssetKind.DATA, AssetPolicy())

    assert "the-admin-token" not in json.dumps(told.workload_config())


def test_the_policy_decides_what_the_grant_pins(config):
    narrow = ConfidentialAsset(
        config,
        "model4",
        AssetKind.MODEL,
        AssetPolicy(
            bind_peer_asset=True, allowed_result_collectors=[Party.DATA_OWNER]
        ),
    )

    narrow.set_permitted([workload()])

    assert narrow.vault.store.permitted() == [
        "scripthash::datahash::modelhash::collectorhash"
    ]


def test_publishing_twice_replaces_rather_than_accumulates(config):
    """An asset's name is derived from the entity, so a republish overwrites"""
    published(config)
    published(config)

    directory = os.path.join(config["root"], "dataset3")

    assert sorted(os.listdir(directory)) == [ASSET_FILE]


def test_permitted_identities_are_recorded_where_a_workload_could_check(config):
    asset = published(config)

    asset.set_permitted([workload()])

    assert os.path.exists(os.path.join(asset.vault.store.directory, PERMITTED_FILE))
