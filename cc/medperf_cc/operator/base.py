"""Running a confidential workload and collecting what it produced.

Transport only: the runner starts the workload, watches it, and fetches its
output. The output stays encrypted, because only the party holding the result
collector's private key can open it, and that party is not the runner.
"""

from abc import ABC, abstractmethod
from typing import Iterator

from medperf_cc.identity import WorkloadIdentity


class WorkloadRunner(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def verify(self) -> None:
        """Fails unless this user can operate workloads here."""

    @abstractmethod
    def result_config(self, workload: WorkloadIdentity) -> dict:
        """Where the workload is to write its output."""

    @abstractmethod
    def start(self, image: str, env: dict) -> None:
        """Starts the workload's container image with `env` in its environment."""

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
