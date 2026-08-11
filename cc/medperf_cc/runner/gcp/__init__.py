"""Running a workload on a Google Confidential Space VM.

The operator's own bucket receives the encrypted results, which is why this
backend needs storage settings of its own: they belong to the operator, not to
either asset owner.
"""

from typing import Iterator

from pydantic import BaseModel

from medperf_cc.backends.gcp import checks
from medperf_cc.backends.gcp.credentials import get_user_credentials
from medperf_cc.errors import ConfigurationError, OperationError
from medperf_cc.identity import WorkloadIdentity
from medperf_cc.runner.base import WorkloadRunner
from medperf_cc.runner.gcp.compute import run_workload, wait_for_workload_completion
from medperf_cc.storage.gcp import client as gcs

GCP_RUNNER = "gcp"

SERVICE_ACCOUNT_USER_ROLE = "roles/iam.serviceAccountUser"
OBJECT_VIEWER_ROLE = "roles/storage.objectViewer"


class GCPRunnerConfig(BaseModel):
    project_id: str
    service_account_name: str
    bucket: str
    vm_name: str
    vm_zone: str
    logs_poll_frequency: int = 30  # seconds

    @property
    def service_account_email(self) -> str:
        return f"{self.service_account_name}@{self.project_id}.iam.gserviceaccount.com"

    class Config:
        extra = "ignore"


class ConfidentialSpaceRunner(WorkloadRunner):
    SETTINGS = GCPRunnerConfig

    def __init__(self, config: dict):
        super().__init__(config)
        self.gcp = GCPRunnerConfig(**config)

    @property
    def backend(self) -> str:
        return GCP_RUNNER

    def verify(self) -> None:
        credentials = get_user_credentials()
        problem = checks.check_user_role_on_service_account(
            credentials, self.gcp.service_account_email, SERVICE_ACCOUNT_USER_ROLE
        ) or checks.check_user_role_on_bucket(
            "user", credentials, self.gcp.bucket, OBJECT_VIEWER_ROLE
        )
        if problem:
            raise ConfigurationError(f"Operator setup verification failed: {problem}")

    def result_config(self, workload: WorkloadIdentity) -> dict:
        return {
            "backend": self.backend,
            "bucket": self.gcp.bucket,
            "encrypted_result_bucket_file": workload.results_path,
            "encrypted_key_bucket_file": workload.results_encryption_key_path,
        }

    def start(self, workload: WorkloadIdentity, image: str, env: dict) -> None:
        metadata = {
            "tee-image-reference": image,
            "tee-container-log-redirect": "true",
        }
        for key, value in env.items():
            metadata[f"tee-env-{key}"] = value

        try:
            run_workload(self.gcp, metadata)
        except Exception:
            raise OperationError(
                "Failed to run workload: User lacks permissions or VM does not exist"
            )

    def wait(self, workload: WorkloadIdentity) -> Iterator[str]:
        return wait_for_workload_completion(self.gcp, workload)

    def results_ready(self, workload: WorkloadIdentity) -> bool:
        if not gcs.file_exists(self.gcp.bucket, workload.results_path):
            return False
        return gcs.file_exists(self.gcp.bucket, workload.results_encryption_key_path)

    def fetch_results(
        self, workload: WorkloadIdentity, encrypted_results_path: str
    ) -> bytes:
        gcs.download_file(
            self.gcp.bucket, workload.results_path, encrypted_results_path
        )
        return gcs.download_string(
            self.gcp.bucket, workload.results_encryption_key_path
        )
