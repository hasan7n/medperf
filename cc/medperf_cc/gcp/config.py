from pydantic import BaseModel


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
