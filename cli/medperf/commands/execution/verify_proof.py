"""Checking the integrity proof attached to a benchmark result.

Answers, without trusting whoever reported the number: were these results
produced by this benchmark's script, on this dataset, with this model, inside
genuine confidential hardware?
"""

import os

import yaml

from medperf import config
from medperf.commands.execution.plan import resolve_plan
from medperf.entities.benchmark import Benchmark
from medperf.entities.dataset import Dataset
from medperf.entities.execution import Execution
from medperf.entities.model import Model
from medperf.exceptions import InvalidArgumentError, MedperfException
from medperf_cc.attestation import TrustAnchor, fetch_google_pki_root
from medperf_cc.proof import (
    IntegrityProof,
    ProofExpectations,
    ProofVerdict,
    verify_proof,
)


def default_pki_root_path() -> str:
    """Where this client keeps its pinned attestation root.

    A client concern rather than a protocol one: `medperf_cc` takes a path and
    knows nothing about MedPerf's storage layout."""
    return os.path.join(str(config.config_storage), "attestation_pki_root.pem")


class VerifyExecutionProof:
    """Verifies one execution's proof against what MedPerf knows it should be."""

    @classmethod
    def run(cls, execution_uid: int, pki_root: str = None) -> ProofVerdict:
        verifier = cls(execution_uid, pki_root)
        verifier.load()
        return verifier.verify()

    def __init__(self, execution_uid: int, pki_root: str = None):
        self.execution_uid = execution_uid
        self.pki_root = pki_root or default_pki_root_path()
        self.execution = None
        self.proof = None

    def load(self):
        self.execution = Execution.get(self.execution_uid)
        self.proof = self.__read_proof()
        if self.proof is None:
            raise InvalidArgumentError(
                f"Execution {self.execution_uid} has no integrity proof."
                " Only confidential executions produce one, and only when the"
                " workload could obtain an attestation."
            )

    def verify(self) -> ProofVerdict:
        return verify_proof(self.proof, self.__trust_anchor(), self.__expectations())

    def __read_proof(self):
        """Prefers the copy the server holds, falling back to the local one."""
        if self.execution.integrity_proof:
            return IntegrityProof.fromdict(self.execution.integrity_proof)

        local = self.execution.integrity_proof_path
        if os.path.exists(local):
            with open(local) as f:
                return IntegrityProof.fromdict(yaml.safe_load(f))
        return None

    def __trust_anchor(self) -> TrustAnchor:
        if not os.path.exists(self.pki_root):
            raise InvalidArgumentError(
                f"No attestation root certificate at {self.pki_root}."
                " Run `medperf result trust_attestation_root` once to pin it."
            )
        return TrustAnchor.from_pki_root_file(self.pki_root)

    def __expectations(self) -> ProofExpectations:
        """What MedPerf's own records say these results should be.

        Taken from the server rather than from the proof: a proof that only
        agreed with itself would establish nothing."""
        plan = resolve_plan(Benchmark.get(self.execution.benchmark))
        dataset = Dataset.get(self.execution.dataset)
        model = Model.get(self.execution.model)

        return ProofExpectations(
            script_image_hash=plan.script.image_hash if plan.script else None,
            data_hash=dataset.generated_uid,
            model_hash=model.asset_obj.asset_hash if model.is_asset() else None,
            results_path=self.__results_path(),
        )

    def __results_path(self):
        """Where the result files are, if this machine still has them.

        Absent for anyone verifying an execution they did not run: the rest of
        the proof still checks, minus the results-match step."""
        outputs = self.execution.local_outputs_path
        return outputs if os.path.isdir(outputs) else None


class TrustAttestationRoot:
    """Pins the attestation PKI root, once, so verification can be offline."""

    @classmethod
    def run(cls, path: str = None) -> str:
        path = path or default_pki_root_path()
        try:
            root = fetch_google_pki_root()
        except Exception as e:
            raise MedperfException(
                f"Could not download the attestation root: {e}"
            )

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(root)
        config.ui.print(f"Attestation root certificate pinned at {path}")
        return path
