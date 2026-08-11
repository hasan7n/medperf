import pytest
from pydantic import ValidationError

from medperf_cc.identity import (
    COLLECTOR_TERM,
    DATA_TERM,
    MODEL_TERM,
    SCRIPT_TERM,
    AssetKind,
)
from medperf_cc.policy import AssetPolicy, Party


@pytest.mark.parametrize("kind", [AssetKind.DATA, AssetKind.MODEL])
def test_an_owner_always_pins_the_script_and_their_own_asset(kind):
    """Anything less would let an arbitrary image, or an image aimed at
    somebody else's asset, decrypt this one"""
    policy = AssetPolicy(bind_peer_asset=False, allowed_result_collectors=[])

    binding = policy.binding(kind)

    assert binding.terms == [SCRIPT_TERM, kind.own_term]


def test_silence_leaves_a_data_owner_pinning_everything():
    binding = AssetPolicy().binding(AssetKind.DATA)

    assert binding.terms == [SCRIPT_TERM, DATA_TERM, MODEL_TERM, COLLECTOR_TERM]


def test_silence_leaves_a_model_owner_pinning_nothing_extra():
    binding = AssetPolicy().binding(AssetKind.MODEL)

    assert binding.terms == [SCRIPT_TERM, MODEL_TERM]


@pytest.mark.parametrize("kind", [AssetKind.DATA, AssetKind.MODEL])
def test_either_kind_of_owner_can_pin_the_peer_asset(kind):
    policy = AssetPolicy(bind_peer_asset=True)

    assert policy.binding(kind).binds(kind.peer_term)


@pytest.mark.parametrize("kind", [AssetKind.DATA, AssetKind.MODEL])
def test_naming_a_collector_is_what_pins_the_collector(kind):
    """An owner cannot restrict who reads the results without saying which key,
    and has no reason to pin a key without restricting"""
    named = AssetPolicy(allowed_result_collectors=[Party.MODEL_OWNER])
    unrestricted = AssetPolicy(allowed_result_collectors=[])

    assert named.binding(kind).binds(COLLECTOR_TERM)
    assert not unrestricted.binding(kind).binds(COLLECTOR_TERM)


def test_terms_come_out_in_canonical_order():
    """The order is what makes two identity strings comparable at all"""
    policy = AssetPolicy(
        bind_peer_asset=True, allowed_result_collectors=[Party.DATA_OWNER]
    )

    assert policy.binding(AssetKind.MODEL).terms == [
        SCRIPT_TERM,
        DATA_TERM,
        MODEL_TERM,
        COLLECTOR_TERM,
    ]


def test_a_repeated_collector_is_named_once():
    policy = AssetPolicy(
        allowed_result_collectors=[Party.DATA_OWNER, Party.DATA_OWNER]
    )

    assert policy.allowed_result_collectors == [Party.DATA_OWNER]


def test_a_misspelled_key_is_refused_rather_than_ignored():
    with pytest.raises(ValidationError):
        AssetPolicy(bind_peer_assets=True)
