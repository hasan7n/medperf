"""Google Cloud key release: KMS wraps the key, IAM decides who may unwrap it.

The workload identity pool is told how to build a workload's identity out of
attestation assertions, and the key is bound to the identities the owner
permits. Both are rendered from the same `WorkloadBinding`, so they cannot end
up describing different sets of terms.
"""

from typing import List

from medperf_cc.errors import ConfigurationError, OperationError
from medperf_cc.gcp import checks
from medperf_cc.gcp.config import GCPAssetConfig
from medperf_cc.gcp.credentials import get_user_credentials
from medperf_cc.gcp.kms import encrypt_with_kms_key, set_kms_iam_policy
from medperf_cc.gcp.storage import (
    set_gcs_iam_policy,
    upload_from_file_object_to_gcs,
    upload_string_to_gcs,
)
from medperf_cc.gcp.workload_identity import update_workload_identity_pool_oidc_provider
from medperf_cc.identity import TERM_CLAIMS, AssetKind
from medperf_cc.policy import AssetPolicy
from medperf_cc.vault.base import AssetVault

GCP_KMS_BACKEND = "gcp_kms"

KMS_DECRYPTER_ROLE = "roles/cloudkms.cryptoKeyDecrypter"
GCS_VIEWER_ROLE = "roles/storage.objectViewer"

# IMPORTANT: https://docs.cloud.google.com/confidential-computing/
# confidential-space/docs/create-grant-access-confidential-resources#attestation-assertions
GOOGLE_SUBJECT_ASSERTION = (
    '"gcpcs::"'
    '+assertion.submods.container.image_digest+"::"'
    '+assertion.submods.gce.project_number+"::"'
    "+assertion.submods.gce.instance_id"
)


def workload_uid_assertion(binding) -> str:
    """The CEL that rebuilds a workload's identity from its attestation.

    `assertion.` is how a workload identity pool addresses a token claim, so
    this is the same claim paths the binding is defined over, in the same
    order, spelled the way Google evaluates them."""
    return '+"::"+'.join(f"assertion.{TERM_CLAIMS[term]}" for term in binding.terms)


class GCPVault(AssetVault):
    def __init__(self, config: dict, kind: AssetKind, policy: AssetPolicy):
        super().__init__(config, kind, policy)
        self.gcp = GCPAssetConfig(**config)

    @property
    def backend(self) -> str:
        return GCP_KMS_BACKEND

    def verify(self) -> None:
        credentials = get_user_credentials()
        # Every check is a network call that returns a message when something
        # is missing, so the chain stops at the first thing that is wrong.
        problem = (
            checks.check_user_role_on_bucket(
                "user", credentials, self.gcp.bucket, "roles/storage.admin"
            )
            or checks.check_user_role_on_kms_key(
                credentials,
                self.gcp.full_key_name,
                "roles/cloudkms.cryptoKeyEncrypter",
            )
            or checks.check_user_role_on_kms_key(
                credentials, self.gcp.full_key_name, "roles/cloudkms.admin"
            )
            or checks.check_user_role_on_wip(
                credentials,
                self.gcp.full_wip_name,
                "roles/iam.workloadIdentityPoolAdmin",
            )
        )
        if problem:
            raise ConfigurationError(
                f"Asset owner setup verification failed: {problem}"
            )

    def publish_key(self, encryption_key: bytes) -> None:
        encrypted_key = encrypt_with_kms_key(self.gcp, encryption_key)
        upload_string_to_gcs(
            self.gcp, encrypted_key, self.gcp.encrypted_key_bucket_file
        )
        self.__update_wip_oidc_provider()

    def publish_asset(self, encrypted_asset_file) -> None:
        upload_from_file_object_to_gcs(
            self.gcp, encrypted_asset_file, self.gcp.encrypted_asset_bucket_file
        )

    def set_permitted_identities(self, identities: List[str]) -> None:
        principals = [self.__principal(identity) for identity in identities]
        set_kms_iam_policy(self.gcp, principals, KMS_DECRYPTER_ROLE)
        set_gcs_iam_policy(self.gcp, principals, GCS_VIEWER_ROLE)

    def __principal(self, identity: str) -> str:
        return (
            f"principalSet://iam.googleapis.com/projects/{self.gcp.project_number}/"
            f"locations/global/workloadIdentityPools/{self.gcp.wip}/"
            f"attribute.workload_uid/{identity}"
        )

    def __update_wip_oidc_provider(self) -> None:
        attribute_mapping = {
            "google.subject": GOOGLE_SUBJECT_ASSERTION,
            "attribute.workload_uid": workload_uid_assertion(self.binding),
        }

        attribute_condition = 'assertion.swname == "CONFIDENTIAL_SPACE"'
        gpu_mode = 'assertion.submods.nvidia_gpu.cc_mode == "ON"'
        stable_image = (
            "'STABLE' in assertion.submods.confidential_space.support_attributes"
        )
        # NOTE: currently it seems that gpu mode is not stable
        attribute_condition += f" && ({gpu_mode} || {stable_image})"

        if self.policy.location:
            attribute_condition += (
                f' && assertion.submods.gce.zone == "{self.policy.location}"'
            )
        if self.policy.hardware:
            attribute_condition += f' && assertion.hwmodel == "{self.policy.hardware}"'

        try:
            update_workload_identity_pool_oidc_provider(
                self.gcp, attribute_mapping, attribute_condition
            )
        except Exception as e:
            raise OperationError(
                f"Failed to update workload identity pool OIDC provider: {e}"
            )
