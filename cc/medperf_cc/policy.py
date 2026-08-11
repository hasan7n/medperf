"""What an asset owner will let a confidential workload do with their asset.

Stated in terms of the workload, never of a particular cloud: each key release
backend translates this into whatever it enforces policy with.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, validator

from medperf_cc.identity import (
    COLLECTOR_TERM,
    SCRIPT_TERM,
    TERM_ORDER,
    AssetKind,
    WorkloadBinding,
)


class Party(Enum):
    """A role in a confidential execution, identified by that party's key."""

    BENCHMARK_OWNER = "benchmark_owner"
    MODEL_OWNER = "model_owner"
    DATA_OWNER = "data_owner"


# What an owner who states no preference gets. Data cannot be un-leaked, so
# silence must not widen who may read it; a model owner's grant is meant to be
# data-agnostic, so pinning a dataset would mean re-authorizing every time one
# joins a benchmark. Both reproduce what each side did before it was a choice.
DEFAULT_BIND_PEER_ASSET = {AssetKind.DATA: True, AssetKind.MODEL: False}
DEFAULT_RESULT_COLLECTORS = {
    AssetKind.DATA: [Party.DATA_OWNER],
    AssetKind.MODEL: [],
}


class AssetPolicy(BaseModel):
    """Where a workload must run, and how narrowly the grant is scoped.

    An owner always pins the benchmark script and their own asset: anything
    less would let an arbitrary image, or an image aimed at somebody else's
    asset, decrypt theirs. The remaining two terms of a workload's identity are
    theirs to choose, and `None` means "no preference" -- the asset kind's
    default, not "off".
    """

    # The cloud region or zone the confidential VM must be running in.
    location: Optional[str] = None
    # The confidential hardware platform, as the attestation reports it.
    hardware: Optional[str] = None
    # Whether to pin the other asset in the execution, rather than allow any.
    bind_peer_asset: Optional[bool] = None
    # Whose keys this owner will let results be encrypted for. Naming any pins
    # the collector: an owner cannot restrict who reads the results without
    # saying which key, and has no reason to pin a key without restricting.
    # Empty means unrestricted, which is the same as not pinning at all.
    allowed_result_collectors: Optional[List[Party]] = None

    class Config:
        # A policy decides who may read an asset. A key the owner misspelled is
        # a policy they did not get, so it is refused rather than ignored.
        extra = "forbid"

    @validator("allowed_result_collectors")
    def unique_collectors(cls, parties):
        if parties is None:
            return None
        return list(dict.fromkeys(parties))

    def binds_peer_asset(self, kind: AssetKind) -> bool:
        if self.bind_peer_asset is None:
            return DEFAULT_BIND_PEER_ASSET[kind]
        return self.bind_peer_asset

    def result_collectors(self, kind: AssetKind) -> List[Party]:
        if self.allowed_result_collectors is None:
            return DEFAULT_RESULT_COLLECTORS[kind]
        return self.allowed_result_collectors

    def binding(self, kind: AssetKind) -> WorkloadBinding:
        terms = {SCRIPT_TERM, kind.own_term}
        if self.binds_peer_asset(kind):
            terms.add(kind.peer_term)
        if self.result_collectors(kind):
            terms.add(COLLECTOR_TERM)
        return WorkloadBinding(terms=[term for term in TERM_ORDER if term in terms])
