"""Running a confidential workload and collecting what it produced.

Transport only: the runner starts the workload, watches it, and fetches its
output. The output stays encrypted, because only the party holding the result
collector's private key can open it, and that party is not the runner.
"""

from abc import ABC, abstractmethod
from typing import Iterator

from medperf_cc.identity import WorkloadIdentity
from medperf_cc.workload import workload_env


class WorkloadRunner(ABC):
    def __init__(self, config: dict):
        self.config = config

    def start(
        self,
        workload: WorkloadIdentity,
        image: str,
        data_config: dict,
        model_config: dict,
        result_collector_public_key: str,
    ) -> None:
        """Starts a workload, told where to fetch its inputs and leave its
        output.

        Where the output goes is this runner's own business -- it belongs to
        the operator, not to either asset owner -- so the caller states what it
        knows and nothing more."""
        self.launch(
            workload,
            image,
            workload_env(
                workload,
                data_config,
                model_config,
                self.result_config(workload),
                result_collector_public_key,
            ),
        )

    @property
    @abstractmethod
    def backend(self) -> str:
        """The name a configuration uses to select this runner."""

    @abstractmethod
    def verify(self) -> None:
        """Fails unless this user can operate workloads here."""

    @abstractmethod
    def result_config(self, workload: WorkloadIdentity) -> dict:
        """Where the workload is to write its output, in this backend's shape."""

    @abstractmethod
    def launch(self, workload: WorkloadIdentity, image: str, env: dict) -> None:
        """Runs the workload's container image with `env` in its environment."""

    @abstractmethod
    def wait(self, workload: WorkloadIdentity) -> Iterator[str]:
        """Yields the workload's log output until it stops."""

    @abstractmethod
    def results_ready(self, workload: WorkloadIdentity) -> bool:
        """Whether the workload's output is there to be fetched."""

    @abstractmethod
    def fetch_results(
        self, workload: WorkloadIdentity, encrypted_results_path: str
    ) -> bytes:
        """Downloads the encrypted results, and returns their encrypted key."""
