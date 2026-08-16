"""Who holds which role in a confidential execution, and whose key collects.

Results are encrypted for a public key, and an asset owner who pins the result
collector is pinning that key. This is where a MedPerf role becomes the hash of
a key, which is the only form the attestation ever sees it in.
"""

import base64
import logging
from typing import List, Optional, Set

from medperf.account_management import get_medperf_user_data, is_user_logged_in
from medperf.cc.config import policy_of
from medperf.commands.certificate.utils import current_user_certificate_status
from medperf.entities.benchmark import Benchmark
from medperf.entities.certificate import Certificate
from medperf.entities.dataset import Dataset
from medperf.entities.model import Model
from medperf.enums import CryptoKeyType
from medperf.exceptions import ExecutionError, MedperfException
from medperf.utils import get_string_hash
from medperf_cc import Party


def public_key_hash(certificate: Certificate) -> str:
    """The result collector identity a workload attests with."""
    public_key_b64 = base64.b64encode(certificate.public_key())
    return get_string_hash(public_key_b64)


def current_user_certificate() -> Certificate:
    """The current user's certificate, issued or merely submitted.

    A certificate that has been issued but not yet uploaded is still the key
    results will be encrypted for, so a fresh user is not blocked on the
    upload."""
    status_dict = current_user_certificate_status(CryptoKeyType.RSA)
    user_cert = None
    if status_dict["should_be_submitted"]:
        user_cert = Certificate.get_local_user_certificate(CryptoKeyType.RSA)
    elif status_dict["no_action_required"]:
        user_cert = status_dict["user_cert_object"]

    if not user_cert:
        raise MedperfException(
            "User must have a certificate to take part in a confidential execution"
        )
    return user_cert


def owner_key_hash(owner_id: int) -> Optional[str]:
    """The key hash of one party, or None if they hold no certificate."""
    if is_user_logged_in() and owner_id == get_medperf_user_data()["id"]:
        return public_key_hash(current_user_certificate())

    certificate = Certificate.get_owner_certificate(owner_id, CryptoKeyType.RSA)
    return public_key_hash(certificate) if certificate else None


def collector_public_key() -> bytes:
    """The key the results of an execution are encrypted for.

    The operator's own: results are encrypted for whoever decrypts them, and
    the operator is the one who downloads them."""
    return base64.b64encode(current_user_certificate().public_key())


def party_owners(
    benchmark: Benchmark, dataset: Dataset = None, model: Model = None
) -> dict:
    """Which user holds each role in one execution."""
    owners = {Party.BENCHMARK_OWNER: benchmark.owner}
    if dataset is not None:
        owners[Party.DATA_OWNER] = dataset.owner
    if model is not None:
        owners[Party.MODEL_OWNER] = model.owner
    return owners


def parties_of(user_id: int, owners: dict) -> Set[Party]:
    """The roles one user holds. Holding any one of the allowed roles is enough."""
    return {party for party, owner_id in owners.items() if owner_id == user_id}


def collector_key_hashes(collectors: List[Party], owners: dict) -> List[str]:
    """The key hashes an owner's grant must cover, one identity each.

    A policy always names at least one collector, so the term is always pinned
    and there is always a key to name. A party with no certificate is skipped:
    their key cannot be pinned because it does not exist yet."""
    hashes = []
    for party in collectors:
        owner_id = owners.get(party)
        if owner_id is None:
            continue
        key_hash = owner_key_hash(owner_id)
        if key_hash is None:
            logging.warning(f"No certificate for the {party.value} of this execution")
            continue
        hashes.append(key_hash)
    return hashes


def check_operator_is_allowed(
    operator_id: int, benchmark_id: int, dataset: Dataset, model: Model
):
    """Refuses an execution neither asset owner would release its results to.

    Both owners must accept the operator, because the workload needs both keys.
    The cloud enforces this too, but only by withholding a key from a VM that
    has already started, which the operator sees as a workload that produces
    nothing.

    Every confidential execution belongs to a benchmark, which is where the
    roles being checked come from."""
    benchmark = Benchmark.get(benchmark_id)
    held = parties_of(operator_id, party_owners(benchmark, dataset, model))

    for label, entity in (("Dataset", dataset), ("Model", model)):
        collectors = policy_of(entity).allowed_result_collectors
        if not held.intersection(collectors):
            allowed = ", ".join(party.value for party in collectors)
            raise ExecutionError(
                f"The {label.lower()} owner only releases results to: {allowed}."
                " The current user holds none of those roles in this execution,"
                " and so cannot operate it."
            )
