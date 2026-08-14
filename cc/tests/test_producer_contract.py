"""One contract, written twice.

The results hash and the statement encoding exist in both `medperf_cc.proof` and
the confidential base image, because the image is built separately with minimal
dependencies and cannot import this package. A silent disagreement between them
would mean every proof fails to verify, with nothing to say why.

So the producer is loaded from source and compared against the verifier
directly. If this fails, one of the two was changed without the other.
"""

import importlib.util
import json
import os
import sys
import types

import yaml

import pytest

from medperf_cc import proof as verifier

PRODUCER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "examples",
    "cc",
    "base_image",
    "src",
    "integrity_proof.py",
)


def load_producer():
    """Loads the base image's module without its runtime dependencies.

    It imports the launcher client and the image's own crypto helpers, neither
    of which exists outside the VM. Both are stubbed with exactly what the
    hashing code uses, so what is compared below is the real producer."""
    import hashlib

    attestation = types.ModuleType("assets.attestation")
    attestation.AttestationUnavailable = type("AttestationUnavailable", (Exception,), {})
    attestation.request_token = lambda **kwargs: ""

    crypto = types.ModuleType("crypto")
    crypto.get_string_hash = lambda value: hashlib.sha256(value.encode()).hexdigest()

    assets = types.ModuleType("assets")
    assets.attestation = attestation

    stubs = {"assets": assets, "assets.attestation": attestation, "crypto": crypto}
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location(
            "base_image_integrity_proof", PRODUCER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                del sys.modules[name]
            else:
                sys.modules[name] = previous


@pytest.fixture(scope="module")
def producer():
    return load_producer()


@pytest.fixture()
def results(tmp_path):
    directory = tmp_path / "results"
    (directory / "nested").mkdir(parents=True)
    (directory / "results.yaml").write_text("auc: 0.91\n")
    (directory / "nested" / "predictions.csv").write_text("1,2,3\n")
    return str(directory)


def test_both_sides_name_the_proof_files_the_same(producer):
    assert producer.STATEMENT_FILE == verifier.STATEMENT_FILE
    assert producer.TOKEN_FILE == verifier.TOKEN_FILE
    assert producer.PROOF_FILES == verifier.PROOF_FILES


def test_both_sides_use_the_same_audience(producer):
    assert producer.PROOF_AUDIENCE == verifier.PROOF_AUDIENCE


def test_the_statement_version_is_one_the_verifier_supports(producer):
    assert producer.STATEMENT_VERSION in verifier.SUPPORTED_STATEMENT_VERSIONS


def test_both_sides_hash_the_result_files_identically(producer, results):
    assert producer.results_files_hash(results) == verifier.results_files_hash(results)


def test_both_sides_exclude_the_proof_files_identically(producer, results):
    with open(os.path.join(results, verifier.STATEMENT_FILE), "w") as f:
        f.write("{}")
    with open(os.path.join(results, verifier.TOKEN_FILE), "w") as f:
        f.write("a.b.c")

    assert producer.results_files_hash(results) == verifier.results_files_hash(results)


def test_both_sides_hash_the_metrics_identically(producer, results):
    """The producer reads a YAML file, the verifier is handed a dict off the
    server. They have to arrive at the same number or nobody can check a
    reported metric"""
    metrics = {"auc": 0.91, "accuracy": 0.8, "nested": {"b": 2, "a": [1, 2]}}
    with open(os.path.join(results, verifier.RESULTS_FILE), "w") as f:
        yaml.safe_dump(metrics, f)

    assert producer.results_hash(results) == verifier.results_hash(metrics)


def test_the_metrics_hash_survives_a_json_round_trip(producer, results):
    """What the verifier gets has been through the server's JSON column, not
    read off a YAML file"""
    metrics = {"auc": 0.91, "labels": ["a", "b"]}
    with open(os.path.join(results, verifier.RESULTS_FILE), "w") as f:
        yaml.safe_dump(metrics, f)

    from_server = json.loads(json.dumps(metrics))

    assert producer.results_hash(results) == verifier.results_hash(from_server)


def test_the_metrics_hash_ignores_how_the_yaml_was_written(producer, results):
    """Key order and formatting are not part of what was computed"""
    path = os.path.join(results, verifier.RESULTS_FILE)
    with open(path, "w") as f:
        f.write("auc: 0.91\naccuracy: 0.8\n")
    one_way = producer.results_hash(results)
    with open(path, "w") as f:
        f.write("accuracy:   0.8\n\nauc: 0.91\n")

    assert producer.results_hash(results) == one_way


def test_a_workload_producing_no_metrics_attests_to_none(producer, tmp_path):
    """An inference_script workload returns predictions, not a score"""
    predictions_only = tmp_path / "predictions"
    predictions_only.mkdir()
    (predictions_only / "preds.csv").write_text("1,2,3\n")

    assert producer.results_hash(str(predictions_only)) is None


def test_both_sides_hash_the_statement_identically(producer):
    """This is the nonce the workload commits to. If the two disagreed, the
    verifier would reject every genuine proof"""
    statement = {
        "version": 1,
        "results_sha256": "a" * 64,
        "data_sha256": "b" * 64,
        "model_sha256": None,
    }

    assert producer.canonical_statement_hash(statement) == verifier.statement_hash(
        statement
    )


def test_the_statement_the_producer_writes_is_the_one_it_committed_to(
    producer, results, monkeypatch, tmp_path
):
    """Serialization must not change the hash: the verifier recomputes it from
    the parsed JSON, not from the bytes on disk"""
    monkeypatch.setenv("TMP_FILES", str(tmp_path))
    statement = producer.build_statement(results)

    with open(os.path.join(results, verifier.STATEMENT_FILE), "w") as f:
        json.dump(statement, f, sort_keys=True, separators=(",", ":"))
    with open(os.path.join(results, verifier.STATEMENT_FILE)) as f:
        parsed = json.load(f)

    assert verifier.statement_hash(parsed) == producer.canonical_statement_hash(
        statement
    )


def test_the_producer_reports_what_the_workload_measured(
    producer, results, monkeypatch, tmp_path
):
    monkeypatch.setenv("TMP_FILES", str(tmp_path))
    with open(tmp_path / producer.MEASURED_HASHES_FILE, "w") as f:
        json.dump({"data_sha256": "measured-data", "model_sha256": "measured-model"}, f)

    statement = producer.build_statement(results)

    assert statement["data_sha256"] == "measured-data"
    assert statement["model_sha256"] == "measured-model"


def test_the_script_is_deliberately_not_in_the_statement(
    producer, results, monkeypatch, tmp_path
):
    """It comes from the token's attested image digest. A workload
    self-reporting its own image would be worth nothing"""
    monkeypatch.setenv("TMP_FILES", str(tmp_path))

    statement = producer.build_statement(results)

    assert "script" not in json.dumps(statement)


def test_both_sides_map_an_undefined_metric_the_same_way(producer, results):
    """`AUC: .nan` is a real output -- an AUC is undefined when the labels hold
    one class. Python spells it `NaN`, which no other JSON reader accepts, so
    it cannot be what either side hashes"""
    with open(os.path.join(results, verifier.RESULTS_FILE), "w") as f:
        f.write("AUC: .nan\nAccuracy: 0.93\n")

    assert producer.results_hash(results) == verifier.results_hash(
        {"AUC": float("nan"), "Accuracy": 0.93}
    )


def test_an_undefined_metric_hashes_as_the_null_it_becomes(producer, results):
    """What a strict JSON store holds after the round trip is null, and that
    has to be what verifies"""
    with open(os.path.join(results, verifier.RESULTS_FILE), "w") as f:
        f.write("AUC: .nan\nAccuracy: 0.93\n")

    assert producer.results_hash(results) == verifier.results_hash(
        {"AUC": None, "Accuracy": 0.93}
    )


def test_what_is_hashed_is_always_readable_by_any_json_reader(producer, results):
    """Belt and braces: `allow_nan=False` means a value that slipped through
    would raise here rather than produce a hash nobody can recompute"""
    with open(os.path.join(results, verifier.RESULTS_FILE), "w") as f:
        f.write("AUC: .inf\nWorse: -.inf\n")

    assert producer.results_hash(results) == verifier.results_hash(
        {"AUC": None, "Worse": None}
    )
