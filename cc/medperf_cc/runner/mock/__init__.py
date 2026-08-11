"""Running the workload as a plain container on this machine.

The same image a confidential VM would run, given the same environment, writing
its output to the same mock storage every other party is using. What is missing
is the VM: nothing is measured, nothing is attested, and the workload could be
anything. Selecting `mock` is selecting "no protection at all".
"""

import logging
import os
import subprocess
from typing import Iterator

from medperf_cc.backends.mock import MOCK, MockConfig, MockStore
from medperf_cc.errors import OperationError
from medperf_cc.identity import WorkloadIdentity
from medperf_cc.runner.base import WorkloadRunner

RESULTS_FILE = "results.enc"
RESULTS_KEY_FILE = "results_key.enc"


class MockRunnerConfig(MockConfig):
    container_runtime: str = "docker"
    # The workload writes as whoever the image says. Running it as this user
    # keeps the results readable once they are back on the host.
    run_as_current_user: bool = True


class MockRunner(WorkloadRunner):
    SETTINGS = MockRunnerConfig

    def __init__(self, config: dict):
        super().__init__(config)
        self.mock = MockRunnerConfig(**config)

    @property
    def backend(self) -> str:
        return MOCK

    def verify(self) -> None:
        try:
            subprocess.run(
                [self.mock.container_runtime, "version"],
                capture_output=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as e:
            raise OperationError(
                f"The mock runner needs {self.mock.container_runtime}"
                f" to start a workload: {e}"
            )
        os.makedirs(self.mock.root, exist_ok=True)

    def result_config(self, workload: WorkloadIdentity) -> dict:
        return {
            "backend": self.backend,
            "root": self.mock.root,
            "results_name": workload.storage_prefix,
        }

    def start(self, workload: WorkloadIdentity, image: str, env: dict) -> None:
        name = self.__container_name(workload)
        os.makedirs(self.mock.root, exist_ok=True)
        self.__remove_container(name)

        command = [
            self.mock.container_runtime,
            "run",
            "--detach",
            "--name",
            name,
            # Mounted at the same path inside, so every path the parties
            # exchanged means the same thing on both sides.
            "--volume",
            f"{self.mock.root}:{self.mock.root}",
            # gnupg wants somewhere to put its keyring
            "--env",
            "HOME=/tmp",
        ]
        if self.mock.run_as_current_user:
            command += ["--user", f"{os.getuid()}:{os.getgid()}"]
        for key, value in env.items():
            command += ["--env", f"{key}={value}"]
        command.append(image)

        started = subprocess.run(command, capture_output=True, text=True)
        if started.returncode != 0:
            raise OperationError(f"Failed to start the workload: {started.stderr}")

    def wait(self, workload: WorkloadIdentity) -> Iterator[str]:
        name = self.__container_name(workload)
        logs = subprocess.Popen(
            [self.mock.container_runtime, "logs", "--follow", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in logs.stdout:
            yield line.rstrip()
        logs.wait()

        exit_code = self.__exit_code(name)
        if exit_code not in (0, None):
            logging.error(f"The workload exited with status {exit_code}")

    def results_ready(self, workload: WorkloadIdentity) -> bool:
        store = self.__results(workload)
        return store.exists(RESULTS_FILE) and store.exists(RESULTS_KEY_FILE)

    def fetch_results(
        self, workload: WorkloadIdentity, encrypted_results_path: str
    ) -> bytes:
        if not self.results_ready(workload):
            raise OperationError(
                f"The workload for {workload.storage_prefix} has produced no"
                " results to fetch"
            )
        store = self.__results(workload)
        with open(encrypted_results_path, "wb") as f:
            f.write(store.read(RESULTS_FILE))
        return store.read(RESULTS_KEY_FILE)

    def __results(self, workload: WorkloadIdentity) -> MockStore:
        return MockStore({"root": self.mock.root}, workload.storage_prefix)

    def __container_name(self, workload: WorkloadIdentity) -> str:
        return f"medperf-cc-mock-{workload.storage_prefix}"

    def __remove_container(self, name: str) -> None:
        subprocess.run(
            [self.mock.container_runtime, "rm", "--force", name], capture_output=True
        )

    def __exit_code(self, name: str):
        inspected = subprocess.run(
            [
                self.mock.container_runtime,
                "inspect",
                "--format",
                "{{.State.ExitCode}}",
                name,
            ],
            capture_output=True,
            text=True,
        )
        if inspected.returncode != 0:
            return None
        try:
            return int(inspected.stdout.strip())
        except ValueError:
            return None
