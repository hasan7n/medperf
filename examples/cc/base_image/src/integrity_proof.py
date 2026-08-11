"""Producing an integrity proof for what this workload computed.

A benchmark result is otherwise a number the operator reports, and everybody
downstream has to take their word for it. This makes it checkable: a statement
naming what went in and what came out, bound to a signed attestation of what
actually ran, verifiable afterwards by anyone holding a pinned root certificate.

No new signing machinery is involved, because the attestation token already
carries most of the statement:

    submods.container.image_digest                       which script ran
    submods.container.env_override.EXPECTED_DATA_HASH    which data it declared
    submods.container.env_override.EXPECTED_MODEL_HASH   which model it declared
    swname / hwmodel / support_attributes                that it was real hardware
    eat_nonce                                            whatever we put there

So the statement's hash goes in the nonce, and the statement travels with the
results. What the token does *not* carry is the inputs as the workload actually
saw them -- `env_override` is operator-supplied and states an expectation, not a
fact. `setup_assets` measures the decrypted inputs and records what it found;
the statement reports those measurements, so a verifier can see the declared and
the measured values agree without having to know that the script checks them.

## The results hash

`results_sha256` covers every file the operator will report, and deliberately
*not* the two proof files, which do not exist yet when it is computed. A
verifier must apply the same exclusion. The algorithm, so it can be
reimplemented exactly:

    sha256 of each file's content, hex
    excluding integrity_statement.json and integrity_token.jwt
    sorted as strings
    concatenated utf-8 and hashed again

It depends on file contents only, never on names or paths, so it survives the
tar and untar the results go through on their way out of the VM.
"""

import argparse
import hashlib
import json
import os
from typing import Optional

from assets.attestation import AttestationUnavailable, request_token
from crypto import get_string_hash

STATEMENT_FILE = "integrity_statement.json"
TOKEN_FILE = "integrity_token.jwt"
PROOF_FILES = {STATEMENT_FILE, TOKEN_FILE}

MEASURED_HASHES_FILE = "measured_hashes.json"

# A proof is meant to be checkable by anyone, so there is no particular relying
# party to name. A fixed, recognizable audience beats a misleading one.
PROOF_AUDIENCE = "https://medperf.org/integrity-proof"

STATEMENT_VERSION = 1


def results_hash(results_path: str) -> str:
    """Hashes the result files, excluding the proof artifacts themselves."""
    hashes = []
    for root, _, files in os.walk(results_path):
        for name in files:
            if name in PROOF_FILES:
                continue
            hashes.append(__file_hash(os.path.join(root, name)))

    digest = hashlib.sha256()
    for each in sorted(hashes):
        digest.update(each.encode("utf-8"))
    return digest.hexdigest()


def canonical_statement_hash(statement: dict) -> str:
    """A hash of the statement that does not depend on how it was serialized."""
    return get_string_hash(
        json.dumps(statement, sort_keys=True, separators=(",", ":"))
    )


def build_statement(results_path: str) -> dict:
    """The hashes of everything involved: what went in, and what came out.

    Data and model are measured inside the VM on the decrypted inputs, so they
    say what was actually read rather than what the operator declared. The
    script is deliberately not in here -- it comes from the token's attested
    `image_digest`, and a workload self-reporting its own image would be worth
    nothing.
    """
    measured = __measured_hashes()
    return {
        "version": STATEMENT_VERSION,
        "results_sha256": results_hash(results_path),
        "data_sha256": measured.get("data_sha256"),
        "model_sha256": measured.get("model_sha256"),
    }


def write_proof(
    results_path: str, token_type: str = "PKI", issuer: str = "google"
) -> Optional[str]:
    """Writes the statement and its attestation into the results directory.

    Returns None if the launcher would not issue a token. A workload that cannot
    prove itself should still deliver its results: an absent proof is visible to
    whoever checks, whereas raising here would turn "unverifiable" into "failed",
    which is the worse trade.
    """
    statement = build_statement(results_path)
    statement_hash = canonical_statement_hash(statement)

    try:
        # PKI by default: the token carries its own certificate chain, so the
        # proof can be checked years later against a pinned root, with no
        # network and regardless of signing key rotation.
        token = request_token(
            audience=PROOF_AUDIENCE,
            nonces=[statement_hash],
            token_type=token_type,
            issuer=issuer,
        )
    except (AttestationUnavailable, ValueError) as e:
        print(f"WARNING: no integrity proof will be produced: {e}")
        return None

    with open(os.path.join(results_path, STATEMENT_FILE), "w") as f:
        json.dump(statement, f, sort_keys=True, separators=(",", ":"))
    with open(os.path.join(results_path, TOKEN_FILE), "w") as f:
        f.write(token)
    return statement_hash


def __file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def __measured_hashes() -> dict:
    path = os.path.join(os.getenv("TMP_FILES", "/tmp/files"), MEASURED_HASHES_FILE)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Write an integrity proof")
    parser.add_argument("--result-files", required=True)
    parser.add_argument("--token-type", default=os.getenv("PROOF_TOKEN_TYPE", "PKI"))
    parser.add_argument("--issuer", default=os.getenv("PROOF_ISSUER", "google"))
    args = parser.parse_args()

    written = write_proof(
        args.result_files, token_type=args.token_type, issuer=args.issuer
    )
    print("Integrity proof written" if written else "Integrity proof unavailable")
