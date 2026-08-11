from typing import Optional

from pydantic import BaseModel


class CCWorkloadID(BaseModel):
    """Identifies a confidential workload.

    Two identities are derived from it, and only the `*_hash` fields take part
    in either. The `*_id` fields exist to build human readable storage paths.

    - `id`: what a data owner's policy binds. It pins all four parties, so a
      data owner authorizes one exact (script, data, model, collector) combination.
    - `id_for_model`: what a model owner's policy binds. It pins only the script
      and the model, so a model owner authorizes an image to load their weights
      regardless of which dataset it is pointed at. Model-side workloads are
      built with `for_model_policy`, which leaves the unused fields empty.
    """

    model_hash: str
    script_hash: str
    model_id: int
    script_id: int
    data_hash: str = ""
    result_collector_hash: str = ""
    data_id: Optional[int] = None
    execution_id: Optional[int] = None

    @classmethod
    def for_model_policy(
        cls, model_hash: str, script_hash: str, model_id: int, script_id: int
    ) -> "CCWorkloadID":
        """Builds a workload carrying only what `id_for_model` consumes."""
        return cls(
            model_hash=model_hash,
            script_hash=script_hash,
            model_id=model_id,
            script_id=script_id,
        )

    @property
    def id(self):
        return "::".join(
            [
                self.script_hash,
                self.data_hash,
                self.model_hash,
                self.result_collector_hash,
            ]
        )

    @property
    def id_for_model(self):
        return "::".join(
            [
                self.script_hash,
                self.model_hash,
            ]
        )

    @property
    def human_readable_id(self):
        if self.execution_id:
            return f"d{self.data_id}-m{self.model_id}-s{self.script_id}-e{self.execution_id}"
        return f"d{self.data_id}-m{self.model_id}-s{self.script_id}"

    @property
    def results_path(self):
        return f"{self.human_readable_id}/output"

    @property
    def results_encryption_key_path(self):
        return f"{self.human_readable_id}/encryption_key"


class GCPOperatorConfig(BaseModel):
    project_id: str
    service_account_name: str
    bucket: str
    vm_name: str
    vm_zone: str
    logs_poll_frequency: int = 30  # seconds

    @property
    def service_account_email(self):
        return f"{self.service_account_name}@{self.project_id}.iam.gserviceaccount.com"


class GCPAssetConfig(BaseModel):
    project_id: str
    project_number: str
    bucket: str
    encrypted_asset_bucket_file: str
    encrypted_key_bucket_file: str
    keyring_name: str
    key_name: str
    key_location: str
    wip: str
    wip_provider: str

    @property
    def full_key_name(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.key_location}/"
            f"keyRings/{self.keyring_name}/cryptoKeys/{self.key_name}"
        )

    @property
    def full_wip_provider_name(self) -> str:
        return (
            f"projects/{self.project_number}/locations/global/"
            f"workloadIdentityPools/{self.wip}/providers/{self.wip_provider}"
        )

    @property
    def full_wip_name(self) -> str:
        return (
            f"projects/{self.project_number}/locations/global/"
            f"workloadIdentityPools/{self.wip}"
        )
