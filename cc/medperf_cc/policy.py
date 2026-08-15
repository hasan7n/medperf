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


class AssetPolicy(BaseModel):
    """Where a workload must run, and how narrowly the grant is scoped.

    An owner always pins the benchmark script and their own asset: anything
    less would let an arbitrary image, or an image aimed at somebody else's
    asset, decrypt theirs. The remaining two terms of a workload's identity are
    theirs to choose.

    A policy means the same thing whichever kind of asset it is attached to.
    What differs between a dataset and a model is only which term is their own
    and which is the peer's, and that follows from the asset, not from the
    policy.
    """

    # The cloud region or zone the confidential VM must be running in.
    location: Optional[str] = None
    # The confidential hardware platform, as the attestation reports it.
    hardware: Optional[str] = None
    # Whether to pin the other asset in the execution, rather than allow any.
    # Pinning is the default: an owner who has not said otherwise authorizes
    # one exact combination, never any peer that comes along.
    bind_peer_asset: bool = True
    # Whose keys this owner will let results be encrypted for. Results are
    # encrypted for whoever operates the execution, so this is really the list
    # of who may operate one involving this asset. It has to name somebody:
    # authorizing nobody is a policy no execution could ever satisfy, and it is
    # far more likely to be an owner who forgot than one who meant it.
    allowed_result_collectors: Optional[List[Party]] = None

    class Config:
        # A policy decides who may read an asset. A key the owner misspelled is
        # a policy they did not get, so it is refused rather than ignored.
        extra = "forbid"

    @validator("allowed_result_collectors", always=True)
    def at_least_one_collector(cls, parties):
        """Refused rather than defaulted: who may read an asset's results is
        not something to guess on an owner's behalf."""
        if not parties:
            raise ValueError(
                "name at least one party allowed to collect results."
                f" One or more of: {', '.join(party.value for party in Party)}"
            )
        return list(dict.fromkeys(parties))

    def binding(self, kind: AssetKind) -> WorkloadBinding:
        """Which terms of a workload's identity this owner pins.

        `kind` says which asset the policy is protecting -- that is what makes
        one of the two asset terms "own" and the other "peer". It is not a
        second source of policy.

        The collector is always pinned, because a policy always names one."""
        terms = {SCRIPT_TERM, kind.own_term, COLLECTOR_TERM}
        if self.bind_peer_asset:
            terms.add(kind.peer_term)
        return WorkloadBinding(terms=[term for term in TERM_ORDER if term in terms])
