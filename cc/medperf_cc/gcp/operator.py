"""Running a workload on a Google Confidential Space VM."""

from typing import Iterator

from medperf_cc.errors import ConfigurationError, OperationError
from medperf_cc.gcp import checks
from medperf_cc.gcp.compute import run_workload, wait_for_workload_completion
from medperf_cc.gcp.config import GCPOperatorConfig
from medperf_cc.gcp.credentials import get_user_credentials
from medperf_cc.gcp.storage import (
    check_gcs_file_exists,
    download_file_from_gcs,
    download_string_from_gcs,
)
from medperf_cc.identity import WorkloadIdentity
from medperf_cc.operator import WorkloadRunner


class ConfidentialSpaceRunner(WorkloadRunner):
    def __init__(self, config: dict):
        super().__init__(config)
        self.gcp = GCPOperatorConfig(**config)

    def verify(self) -> None:
        credentials = get_user_credentials()
        problem = checks.check_user_role_on_service_account(
            credentials, self.gcp.service_account_email, "roles/iam.serviceAccountUser"
        ) or checks.check_user_role_on_bucket(
            "user", credentials, self.gcp.bucket, "roles/storage.objectViewer"
        )
        if problem:
            raise ConfigurationError(f"Operator setup verification failed: {problem}")

    def result_config(self, workload: WorkloadIdentity) -> dict:
        return {
            "bucket": self.gcp.bucket,
            "encrypted_result_bucket_file": workload.results_path,
            "encrypted_key_bucket_file": workload.results_encryption_key_path,
        }

    def start(self, image: str, env: dict) -> None:
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
        results_exist = check_gcs_file_exists(self.gcp, workload.results_path)
        if not results_exist:
            return False
        return check_gcs_file_exists(self.gcp, workload.results_encryption_key_path)

    def fetch_results(
        self, workload: WorkloadIdentity, encrypted_results_path: str
    ) -> bytes:
        download_file_from_gcs(
            self.gcp, workload.results_path, encrypted_results_path
        )
        return download_string_from_gcs(
            self.gcp, workload.results_encryption_key_path
        )
