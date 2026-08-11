"""Checking that a result is what it claims to be.

A workload writes a statement naming what it consumed and what it produced, and
an attestation token whose nonce is that statement's hash. Together they
establish which script ran, on which inputs, producing exactly these bytes,
inside genuine confidential hardware -- without trusting whoever reported them.

Not established: that the script computed the metric correctly. Attestation
pins which code ran, never that the code is right.

Verification is offline for PKI tokens. Expiry is deliberately not checked: a
proof records a run that already happened, and a one-hour token that had to
still be current would make every proof self-destruct.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from medperf_cc.attestation.token import AttestationToken, TokenType
from medperf_cc.attestation.verifier import (
    AttestationRequirements,
    TrustAnchor,
    verify_token,
)
from medperf_cc.errors import AttestationError

STATEMENT_FILE = "integrity_statement.json"
TOKEN_FILE = "integrity_token.jwt"
PROOF_FILES = {STATEMENT_FILE, TOKEN_FILE}

# A proof is meant to be checkable by anyone, so there is no particular relying
# party to name. A fixed, recognizable audience beats a misleading one.
PROOF_AUDIENCE = "https://medperf.org/integrity-proof"
SUPPORTED_STATEMENT_VERSIONS = {1}


def results_hash(results_path: str) -> str:
    """Hashes result files the way the workload did.

    Must match the confidential base image exactly: sha256 of each file's
    content as hex, excluding the two proof files, sorted as strings,
    concatenated utf-8 and hashed again. Content only, never names or paths, so
    it survives the tar and untar on the way out of the VM.
    """
    hashes = []
    for root, _, files in os.walk(results_path):
        for name in files:
            if name in PROOF_FILES:
                continue
            hashes.append(file_hash(os.path.join(root, name)))

    digest = hashlib.sha256()
    for each in sorted(hashes):
        digest.update(each.encode("utf-8"))
    return digest.hexdigest()


def file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def statement_hash(statement: dict) -> str:
    """The nonce the workload committed to."""
    canonical = json.dumps(statement, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class IntegrityProof:
    statement: dict
    token: str

    @classmethod
    def from_results_dir(cls, results_path: str) -> Optional["IntegrityProof"]:
        """Reads a proof, or None if the workload did not produce one."""
        statement_path = os.path.join(results_path, STATEMENT_FILE)
        token_path = os.path.join(results_path, TOKEN_FILE)
        if not (os.path.exists(statement_path) and os.path.exists(token_path)):
            return None

        with open(statement_path) as f:
            statement = json.load(f)
        with open(token_path) as f:
            return cls(statement=statement, token=f.read().strip())

    @classmethod
    def fromdict(cls, payload: dict) -> "IntegrityProof":
        return cls(statement=payload["statement"], token=payload["token"])

    def todict(self) -> dict:
        return {"statement": self.statement, "token": self.token}


@dataclass
class ProofExpectations:
    """What the results are supposed to be, according to the caller's records.

    Every field is optional so that a proof can be inspected on its own, but a
    verification that checks nothing is not a verification: supply what you
    know. Taking any of these from the proof itself would establish nothing.
    """

    script_image_hash: Optional[str] = None
    data_hash: Optional[str] = None
    model_hash: Optional[str] = None
    results_path: Optional[str] = None


@dataclass
class ProofVerdict:
    verified: bool
    checks: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    token: Optional[AttestationToken] = None

    @property
    def summary(self) -> str:
        if self.verified:
            return "Results are backed by a valid integrity proof"
        return "; ".join(self.failures) or "Integrity proof could not be verified"


def verify_proof(
    proof: IntegrityProof, anchor: TrustAnchor, expectations: ProofExpectations
) -> ProofVerdict:
    """Verifies a proof and reports every check, passed or failed.

    Collects failures rather than raising on the first, because which part is
    wrong is the useful output: a results hash that does not match means
    something quite different from an image digest that does not match.
    """
    verdict = ProofVerdict(verified=False)

    try:
        token = verify_token(
            proof.token,
            anchor,
            AttestationRequirements(
                audience=PROOF_AUDIENCE,
                nonce=statement_hash(proof.statement),
                allowed_token_types=[TokenType.PKI, TokenType.OIDC],
                # A proof is a record of a run that already happened.
                check_expiry=False,
            ),
        )
    except AttestationError as e:
        verdict.failures.append(str(e))
        return verdict

    verdict.token = token
    verdict.checks.append("Attestation token is genuine and signed by the issuer")
    verdict.checks.append("Statement is the one the workload committed to")

    __check_statement_version(proof.statement, verdict)
    __check_results(proof.statement, expectations, verdict)
    __check_script(token, expectations, verdict)
    __check_inputs(proof.statement, token, expectations, verdict)

    verdict.verified = not verdict.failures
    return verdict


def __check_statement_version(statement: dict, verdict: ProofVerdict):
    version = statement.get("version")
    if version not in SUPPORTED_STATEMENT_VERSIONS:
        verdict.failures.append(f"Unsupported integrity statement version {version!r}")


def __check_results(
    statement: dict, expectations: ProofExpectations, verdict: ProofVerdict
):
    if expectations.results_path is None:
        return

    actual = results_hash(expectations.results_path)
    if actual != statement.get("results_sha256"):
        verdict.failures.append(
            "Results do not match the proof: the statement attests to"
            f" {statement.get('results_sha256')}, these results hash to {actual}"
        )
    else:
        verdict.checks.append("Results are exactly the bytes the workload attested to")


def __check_script(
    token: AttestationToken, expectations: ProofExpectations, verdict: ProofVerdict
):
    """Which code ran. Taken from the attested image digest, never from the
    statement: a workload self-reporting its own image would be worth nothing."""
    if expectations.script_image_hash is None:
        return

    if token.image_digest != expectations.script_image_hash:
        verdict.failures.append(
            f"Results were produced by image {token.image_digest}, not the"
            f" expected script {expectations.script_image_hash}"
        )
    else:
        verdict.checks.append("Produced by the expected script image")


def __check_inputs(
    statement: dict,
    token: AttestationToken,
    expectations: ProofExpectations,
    verdict: ProofVerdict,
):
    """What it ran on, declared and measured.

    The declaration is operator-supplied and lives in the attested environment;
    the measurement was taken inside the VM on the decrypted input. Agreement is
    what makes the declaration trustworthy without knowing the asset owners'
    policies."""
    environment = token.env_override
    inputs = (
        ("data", expectations.data_hash, "EXPECTED_DATA_HASH", "data_sha256"),
        ("model", expectations.model_hash, "EXPECTED_MODEL_HASH", "model_sha256"),
    )

    for label, expected, claim, measured_key in inputs:
        if expected is None:
            continue

        declared = environment.get(claim)
        if declared != expected:
            verdict.failures.append(
                f"Workload ran on a different {label}: attested {declared},"
                f" expected {expected}"
            )
            continue

        measured = statement.get(measured_key)
        if measured is not None and measured != expected:
            verdict.failures.append(
                f"The {label} the workload measured ({measured}) is not the one"
                f" it declared ({expected})"
            )
        else:
            verdict.checks.append(f"Ran on the expected {label}")
