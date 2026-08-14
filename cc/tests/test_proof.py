import json
import os

import pytest

from medperf_cc.proof import (
    IntegrityProof,
    ProofExpectations,
    results_hash,
    verify_proof,
)
from medperf_cc.statement import (
    PROOF_AUDIENCE,
    RESULTS_FILE,
    STATEMENT_FILE,
    TOKEN_FILE,
    results_files_hash,
    statement_hash,
)
from medperf_cc.attestation import TrustAnchor
from medperf_cc.testing import FakeAttestationAuthority, confidential_space_claims

# `verify_proof` resolves what to trust from the name of an authority, and
# fetches its root. Standing in a throwaway one is how these tests get a proof
# that verifies without reaching Google.
TEST_AUTHORITY = "test-authority"

SCRIPT_IMAGE = "sha256:scripthash"
DATA_HASH = "datahash"
MODEL_HASH = "modelhash"


@pytest.fixture()
def authority():
    return FakeAttestationAuthority()


@pytest.fixture(autouse=True)
def anchor(mocker, authority):
    return mocker.patch(
        "medperf_cc.proof.trust_anchor",
        return_value=TrustAnchor(pki_root_pem=authority.root_pem),
    )


METRICS = {"auc": 0.91}


@pytest.fixture()
def results(tmp_path):
    directory = tmp_path / "results"
    directory.mkdir()
    (directory / RESULTS_FILE).write_text("auc: 0.91\n")
    (directory / "extra.txt").write_text("something else\n")
    return directory


def statement(results_dir, **overrides):
    body = {
        "version": 2,
        "results_sha256": results_hash(METRICS),
        "results_files_sha256": results_files_hash(str(results_dir)),
        "data_sha256": DATA_HASH,
        "model_sha256": MODEL_HASH,
    }
    body.update(overrides)
    return body


def proof_for(authority, body, **claim_overrides):
    claims = confidential_space_claims(
        aud=PROOF_AUDIENCE, eat_nonce=statement_hash(body), **claim_overrides
    )
    return IntegrityProof(statement=body, token=authority.mint(claims))


def expectations(results_dir=None, **overrides):
    fields = {
        "script_image_hash": SCRIPT_IMAGE,
        "data_hash": DATA_HASH,
        "model_hash": MODEL_HASH,
        "results": METRICS,
        "results_path": str(results_dir) if results_dir else None,
    }
    fields.update(overrides)
    return ProofExpectations(**fields)


def test_a_proof_of_this_run_verifies(authority, results):
    proof = proof_for(authority, statement(results))

    verdict = verify_proof(proof, expectations(results))

    assert verdict.verified, verdict.failures
    assert "Result files are exactly the bytes the workload produced" in verdict.checks
    assert (
        "Reported metrics are exactly the ones the workload computed" in verdict.checks
    )


def test_editing_the_results_afterwards_is_caught(authority, results):
    proof = proof_for(authority, statement(results))
    (results / "results.yaml").write_text("auc: 0.99\n")

    verdict = verify_proof(proof, expectations(results))

    assert not verdict.verified
    assert any("Result files do not match" in failure for failure in verdict.failures)


def test_adding_a_result_file_afterwards_is_caught(authority, results):
    proof = proof_for(authority, statement(results))
    (results / "sneaked_in.txt").write_text("extra\n")

    verdict = verify_proof(proof, expectations(results))

    assert not verdict.verified


def test_editing_the_statement_afterwards_is_caught(authority, results):
    """The statement's hash is the token's nonce, so changing one word of it
    detaches it from the attestation"""
    proof = proof_for(authority, statement(results))
    proof.statement["results_sha256"] = "something-more-convenient"

    verdict = verify_proof(proof, expectations(results))

    assert not verdict.verified
    assert any("nonce" in failure for failure in verdict.failures)


def test_a_proof_from_another_authority_is_refused(results):
    proof = proof_for(FakeAttestationAuthority(), statement(results))

    verdict = verify_proof(proof, expectations(results))

    assert not verdict.verified


def test_a_different_script_is_caught(authority, results):
    """Which code ran comes from the attested image digest, so a workload
    cannot claim to have been the benchmark's script"""
    proof = proof_for(authority, statement(results))

    verdict = verify_proof(
        proof, expectations(results, script_image_hash="sha256:otherscript")
    )

    assert not verdict.verified
    assert any("produced by image" in failure for failure in verdict.failures)


def test_a_different_dataset_is_caught(authority, results):
    proof = proof_for(authority, statement(results))

    verdict = verify_proof(
        proof, expectations(results, data_hash="a-different-dataset")
    )

    assert not verdict.verified
    assert any("different data" in failure for failure in verdict.failures)


def test_a_workload_that_read_something_else_than_it_declared_is_caught(
    authority, results
):
    """The declaration is operator-supplied; the measurement was taken inside
    the VM. Only their agreement makes the declaration worth anything"""
    proof = proof_for(
        authority, statement(results, data_sha256="what-was-actually-read")
    )

    verdict = verify_proof(proof, expectations(results))

    assert not verdict.verified
    assert any("measured" in failure for failure in verdict.failures)


def test_an_unknown_statement_version_is_refused(authority, results):
    proof = proof_for(authority, statement(results, version=99))

    verdict = verify_proof(proof, expectations(results))

    assert not verdict.verified


def test_a_proof_outlives_the_token_that_carries_it(authority, results):
    """A proof records a run that already happened. A one-hour token that had
    to still be current would make every proof self-destruct"""
    import time

    past = int(time.time()) - 90 * 24 * 3600
    body = statement(results)
    proof = proof_for(authority, body, iat=past, exp=past + 3600)

    verdict = verify_proof(proof, expectations(results))

    assert verdict.verified, verdict.failures


def test_a_proof_can_be_checked_without_the_result_files(authority, results):
    """The common case: somebody reading a number off the server. They cannot
    hash files they do not have, but the metric itself still checks"""
    proof = proof_for(authority, statement(results))

    verdict = verify_proof(proof, expectations(results_dir=None))

    assert verdict.verified, verdict.failures
    assert not any("Result files" in check for check in verdict.checks)
    assert any("Reported metrics" in check for check in verdict.checks)


def test_a_reported_metric_that_was_edited_is_caught(authority, results):
    """The whole point: the number on the server is the number computed"""
    proof = proof_for(authority, statement(results))

    verdict = verify_proof(proof, expectations(results_dir=None, results={"auc": 0.99}))

    assert not verdict.verified
    assert any("Reported metrics do not match" in f for f in verdict.failures)


def test_metrics_check_the_same_however_the_dict_was_ordered(authority, results):
    """It arrives as JSON off a database, not as the file that was written"""
    metrics = {"b": 2, "a": 1}
    body = statement(results, results_sha256=results_hash(metrics))
    proof = proof_for(authority, body)

    verdict = verify_proof(
        proof, expectations(results_dir=None, results={"a": 1, "b": 2})
    )

    assert verdict.verified, verdict.failures


def test_metrics_reported_for_a_workload_that_attested_to_none(authority, results):
    """A predictions-only workload cannot vouch for a metric somebody reports"""
    body = statement(results, results_sha256=None)
    proof = proof_for(authority, body)

    verdict = verify_proof(proof, expectations(results_dir=None))

    assert not verdict.verified
    assert any("attested to no metrics" in f for f in verdict.failures)


def test_every_failure_is_reported_not_just_the_first(authority, results):
    """Which part is wrong is the useful output"""
    proof = proof_for(authority, statement(results))
    (results / RESULTS_FILE).write_text("auc: 0.99\n")

    verdict = verify_proof(
        proof, expectations(results, script_image_hash="sha256:otherscript")
    )

    assert len(verdict.failures) == 2


def test_the_proof_files_are_not_part_of_the_results_hash(results):
    """They do not exist yet when the producer computes it"""
    before = results_files_hash(str(results))
    (results / STATEMENT_FILE).write_text("{}")
    (results / TOKEN_FILE).write_text("a.b.c")

    assert results_files_hash(str(results)) == before


def test_the_results_files_hash_ignores_names_and_paths(tmp_path):
    """It has to survive the tar and untar on the way out of the VM"""
    first = tmp_path / "a"
    (first / "nested").mkdir(parents=True)
    (first / "nested" / "one.txt").write_text("content")

    second = tmp_path / "b"
    second.mkdir()
    (second / "renamed.txt").write_text("content")

    assert results_files_hash(str(first)) == results_files_hash(str(second))


def test_a_proof_round_trips_through_a_results_directory(authority, results):
    proof = proof_for(authority, statement(results))
    (results / STATEMENT_FILE).write_text(json.dumps(proof.statement))
    (results / TOKEN_FILE).write_text(proof.token)

    read_back = IntegrityProof.from_results_dir(str(results))

    assert read_back.statement == proof.statement
    assert read_back.token == proof.token


def test_no_proof_where_the_workload_wrote_none(results):
    assert IntegrityProof.from_results_dir(str(results)) is None
    assert IntegrityProof.from_results_dir(os.path.join(str(results), "nope")) is None
