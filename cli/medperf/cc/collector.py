"""Whoever the results of a confidential execution are for.

The operator supplies the machine. The collector is the party whose key the
results are encrypted for and whose storage they are written to, and only they
can ever open them -- which is what lets the two be different people.

A party, not a backend: `medperf_cc.ResultStore` is the place the results land,
built from the `settings` below.
"""

import base64
from dataclasses import dataclass

import medperf.config as medperf_config
from medperf.account_management import get_medperf_user_object
from medperf.cc.config import policy_of
from medperf.cc.parties import (
    certificate_of,
    current_user_public_key,
    is_current_user,
    parties_of,
    party_owners,
)
from medperf.entities.benchmark import Benchmark
from medperf.entities.dataset import Dataset
from medperf.entities.model import Model
from medperf.exceptions import ExecutionError
from medperf.utils import get_string_hash
from medperf_cc import Party


@dataclass
class CollectorParty:
    user_id: int
    party: Party
    public_key: bytes
    settings: dict

    @property
    def key_hash(self) -> str:
        """The identity the workload attests the results are for."""
        return get_string_hash(self.public_key)


def resolve_collector(
    benchmark: Benchmark, dataset: Dataset, model: Model
) -> CollectorParty:
    """The one party both asset owners will release results to.

    Each owner names the roles they accept; the results are encrypted for a
    single key, so it has to be a role they both named. Two candidates is not a
    choice this can make on anybody's behalf, and none means the owners have
    not agreed -- both are refused rather than guessed at.
    """
    owners = party_owners(benchmark, dataset, model)
    accepted = [
        party
        for party in policy_of(dataset).allowed_result_collectors
        if party in policy_of(model).allowed_result_collectors
    ]

    # Two roles held by one person are one candidate, not two.
    candidates = {}
    for party in accepted:
        owner_id = owners.get(party)
        if owner_id is not None:
            candidates.setdefault(owner_id, party)

    if not candidates:
        raise ExecutionError(
            "The dataset owner and the model owner have not agreed on anybody"
            " to release results to. The dataset owner accepts"
            f" {__roles(dataset)}; the model owner accepts {__roles(model)}."
        )
    if len(candidates) > 1:
        named = ", ".join(sorted(party.value for party in candidates.values()))
        raise ExecutionError(
            f"Both asset owners release results to more than one party: {named}."
            " Results are encrypted for a single key, so exactly one of them"
            " has to be chosen. Narrow one of the policies."
        )

    user_id, party = next(iter(candidates.items()))
    return collector_party(benchmark, user_id, party)


def collector_recorded_as(
    benchmark: Benchmark, dataset: Dataset, model: Model, user_id: int
) -> CollectorParty:
    """The collector an execution was recorded as being for.

    The recorded id is the fact: it is what the server enforces, and it was
    written when the workload was launched. Policies can be edited afterwards,
    so re-deriving one now could name somebody the execution was never run for
    -- and their key is not the key the results were sealed with.

    Their role is still worked out, because it is what says which listing
    publishes their key to the other parties.
    """
    roles = parties_of(user_id, party_owners(benchmark, dataset, model))
    party = next(
        (
            candidate
            for candidate in (Party.DATA_OWNER, Party.MODEL_OWNER)
            if candidate in roles
        ),
        None,
    )
    if party is None:
        raise ExecutionError(
            f"This execution was recorded as collected by user {user_id}, who"
            " owns neither the dataset nor the model, so nothing publishes"
            " their key."
        )
    return collector_party(benchmark, user_id, party)


def collector_party(
    benchmark: Benchmark, user_id: int, party: Party
) -> CollectorParty:
    return CollectorParty(
        user_id=user_id,
        party=party,
        public_key=__public_key(benchmark, user_id, party),
        settings=__settings(user_id, party),
    )


def __roles(entity) -> str:
    return ", ".join(
        party.value for party in policy_of(entity).allowed_result_collectors
    )


def __public_key(benchmark: Benchmark, user_id: int, party: Party) -> bytes:
    if is_current_user(user_id):
        return current_user_public_key()
    certificate = certificate_of(benchmark.id, user_id, party)
    return base64.b64encode(certificate.public_key())


def __settings(user_id: int, party: Party) -> dict:
    """Where this collector receives results.

    Their own, wherever they are. The operator has to know it to tell the
    workload where to write, so it is read from what the server publishes about
    them rather than from anything they hand over -- and it carries an address
    only, never their credentials."""
    if is_current_user(user_id):
        metadata = get_medperf_user_object().metadata
    else:
        metadata = medperf_config.comms.get_user_metadata(user_id)

    settings = (metadata or {}).get("cc", {}).get("collector", {})
    if not settings:
        raise ExecutionError(
            f"Results are to be released to the {party.value}, but they have"
            " not configured anywhere to receive them."
        )
    return settings
