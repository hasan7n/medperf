"""Which entity field is authoritative for each part of a proof.

This mapping is what decides whether a verification means anything: taking any
of it from the proof itself would establish nothing, so each expectation has to
come from MedPerf's own record of what should have run.
"""

import pytest
import yaml

from medperf.commands.execution.verify_proof import VerifyExecutionProof
from medperf.enums import BenchmarkTopology
from medperf.exceptions import InvalidArgumentError
from medperf.tests.mocks.benchmark import TestBenchmark
from medperf.tests.mocks.cube import TestCube
from medperf.tests.mocks.dataset import TestDataset
from medperf.tests.mocks.execution import TestExecution
from medperf.tests.mocks.model import TestAssetModel, TestContainerModel

PATCH_VERIFY = "medperf.commands.execution.verify_proof.{}"

SCRIPT_IMAGE = "sha256:scripthash"
DATA_UID = "the-generated-uid"
ASSET_HASH = "the-asset-hash"

PKI_ROOT = "/pinned/attestation_root.pem"
PROOF = {"statement": {"version": 1}, "token": "from-the-server"}


@pytest.fixture()
def execution(mocker, fs):
    """A registered execution and the three entities it points at."""
    execution = TestExecution(benchmark=1, dataset=2, model=3)
    fs.create_file(PKI_ROOT, contents="-----BEGIN CERTIFICATE-----")

    mocker.patch(PATCH_VERIFY.format("Execution.get"), return_value=execution)
    mocker.patch(
        PATCH_VERIFY.format("Benchmark.get"),
        return_value=TestBenchmark(
            topology=BenchmarkTopology.END_TO_END_SCRIPT.value,
            data_evaluator_mlcube=None,
            benchmark_script=7,
        ),
    )
    mocker.patch(
        PATCH_VERIFY.format("Dataset.get"),
        return_value=TestDataset(generated_uid=DATA_UID),
    )
    mocker.patch(
        PATCH_VERIFY.format("Model.get"),
        return_value=TestAssetModel(
            asset={
                "id": 5,
                "name": "asset",
                "asset_hash": ASSET_HASH,
                "asset_url": "https://test.com/asset.tar.gz",
                "state": "OPERATION",
                "is_valid": True,
            }
        ),
    )
    mocker.patch(
        "medperf.commands.execution.plan.Cube.get",
        return_value=TestCube(id=7, image_hash=SCRIPT_IMAGE),
    )
    return execution


@pytest.fixture()
def verify(mocker):
    """Captures what the verifier was asked to check, and against what."""
    mocker.patch(PATCH_VERIFY.format("TrustAnchor.from_pki_root_file"))
    return mocker.patch(PATCH_VERIFY.format("verify_proof"))


def test_expectations_come_from_medperf_not_from_the_proof(execution, verify):
    """A proof that only agreed with itself would establish nothing"""
    # Arrange
    execution.integrity_proof = PROOF

    # Act
    VerifyExecutionProof.run(execution.id, pki_root=PKI_ROOT)

    # Assert
    expectations = verify.call_args.args[2]
    assert expectations.script_image_hash == SCRIPT_IMAGE
    assert expectations.data_hash == DATA_UID
    assert expectations.model_hash == ASSET_HASH


def test_a_container_model_has_no_asset_hash_to_expect(mocker, execution, verify):
    """Only asset models are loaded into a confidential VM, so there is nothing
    to pin for one that brings its own container"""
    # Arrange
    execution.integrity_proof = PROOF
    mocker.patch(PATCH_VERIFY.format("Model.get"), return_value=TestContainerModel())

    # Act
    VerifyExecutionProof.run(execution.id, pki_root=PKI_ROOT)

    # Assert
    assert verify.call_args.args[2].model_hash is None


def test_results_are_only_checked_where_they_still_are(execution, verify):
    """Anyone verifying an execution they did not run has no files to hash"""
    # Arrange
    execution.integrity_proof = PROOF

    # Act
    VerifyExecutionProof.run(execution.id, pki_root=PKI_ROOT)

    # Assert
    assert verify.call_args.args[2].results_path is None


def test_the_server_copy_of_the_proof_is_preferred(fs, execution, verify):
    """The local copy is what this machine happens to still hold; the server's
    is what everyone else would check"""
    # Arrange
    execution.integrity_proof = PROOF
    fs.create_file(
        execution.integrity_proof_path,
        contents=yaml.safe_dump({"statement": {}, "token": "from-this-machine"}),
    )

    # Act
    VerifyExecutionProof.run(execution.id, pki_root=PKI_ROOT)

    # Assert
    assert verify.call_args.args[0].token == "from-the-server"


def test_a_local_proof_is_used_when_the_server_has_none(fs, execution, verify):
    # Arrange
    execution.integrity_proof = {}
    fs.create_file(
        execution.integrity_proof_path,
        contents=yaml.safe_dump({"statement": {}, "token": "from-this-machine"}),
    )

    # Act
    VerifyExecutionProof.run(execution.id, pki_root=PKI_ROOT)

    # Assert
    assert verify.call_args.args[0].token == "from-this-machine"


def test_an_execution_with_no_proof_is_visibly_unverified(execution, verify):
    # Arrange
    execution.integrity_proof = {}

    # Act & Assert
    with pytest.raises(InvalidArgumentError, match="no integrity proof"):
        VerifyExecutionProof.run(execution.id, pki_root=PKI_ROOT)


def test_verification_refuses_to_run_without_a_pinned_root(execution, verify):
    """A verifier that downloads what it verifies against is not verifying"""
    # Arrange
    execution.integrity_proof = PROOF

    # Act & Assert
    with pytest.raises(InvalidArgumentError, match="trust_attestation_root"):
        VerifyExecutionProof.run(execution.id, pki_root="/nowhere/absent.pem")
