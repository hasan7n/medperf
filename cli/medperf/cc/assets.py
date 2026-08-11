"""Preparing a dataset or a model for confidential execution.

Encryption happens here rather than inside `medperf_cc`: the key is the asset
owner's, so it never has to leave the client. The components downstream only
transport the ciphertext and decide which workloads may have the key.
"""

import os
import secrets

from tqdm import tqdm

from medperf import config as medperf_config
from medperf.cc.errors import as_medperf_error
from medperf.encryption import SymmetricEncryption
from medperf.entities.dataset import Dataset
from medperf.entities.model import Model
from medperf.exceptions import MedperfException
from medperf.utils import (
    generate_tmp_path,
    remove_path,
    secure_write_to_file,
    tar,
    tmp_path_for_cc_asset_key,
)
from medperf_cc.asset_policy_manager import AssetPolicyManager
from medperf_cc.asset_storage_manager import AssetStorageManager
from medperf_cc.gcp import CCWorkloadID


def generate_encryption_key():
    return secrets.token_bytes(32)


@as_medperf_error()
def setup_dataset_for_cc(dataset: Dataset):
    if not dataset.is_cc_configured():
        return
    cc_config = dataset.get_cc_config()
    cc_policy = dataset.get_cc_policy()
    __verify_cloud_environment(cc_config)

    # policy setup
    medperf_config.ui.text = "Generating encryption key"
    encryption_key = generate_encryption_key()
    __setup_policy(cc_config, cc_policy, encryption_key)

    # storage
    medperf_config.ui.text = "Compressing dataset"
    asset_path = generate_tmp_path()
    tar(asset_path, [dataset.data_path, dataset.labels_path])
    __store_asset(cc_config, asset_path, encryption_key)
    del encryption_key
    remove_path(asset_path)


@as_medperf_error()
def setup_model_for_cc(model: Model):
    if not model.is_cc_configured():
        return
    cc_config = model.get_cc_config()
    cc_policy = model.get_cc_policy()
    if not model.is_asset():
        raise MedperfException(
            f"Model {model.id} is not a file-based asset and cannot be set up for confidential computing."
        )
    asset = model.asset_obj
    asset_path = asset.get_archive_path()

    __verify_cloud_environment(cc_config)

    # policy setup
    medperf_config.ui.text = "Generating encryption key"
    encryption_key = generate_encryption_key()
    __setup_policy(cc_config, cc_policy, encryption_key, for_model=True)

    # storage
    __store_asset(cc_config, asset_path, encryption_key)
    del encryption_key


@as_medperf_error()
def update_dataset_cc_policy(dataset: Dataset, permitted_workloads: list[CCWorkloadID]):
    if not dataset.is_cc_configured():
        raise MedperfException(
            f"Dataset {dataset.id} does not have a configuration for confidential computing."
        )

    cc_config = dataset.get_cc_config()
    asset_policy_manager = AssetPolicyManager(cc_config)
    asset_policy_manager.configure_policy(permitted_workloads)


@as_medperf_error()
def update_model_cc_policy(model: Model, permitted_workloads: list[CCWorkloadID]):
    if not model.is_cc_configured():
        raise MedperfException(
            f"Model {model.id} does not have a configuration for confidential computing."
        )
    cc_config = model.get_cc_config()
    if not model.is_asset():
        raise MedperfException(
            f"Model {model.id} is not a file-based asset and cannot be set up for confidential computing."
        )

    asset_policy_manager = AssetPolicyManager(cc_config, for_model=True)
    asset_policy_manager.configure_policy(permitted_workloads)


def sync_cc_metadata(entity, update_comms_fn):
    """Records on the server that the entity's cloud policy is now up to date.

    Called after the cloud policy has been written, so a failure here leaves the
    server thinking the policy is staler than it is — the safe direction."""
    entity.set_last_synced()
    body = {"user_metadata": entity.user_metadata}
    update_comms_fn(entity.id, body)


def __verify_cloud_environment(cc_config: dict):
    medperf_config.ui.text = "Verifying Cloud Environment"
    AssetStorageManager(cc_config).setup()


def __setup_policy(
    cc_config: dict, cc_policy: dict, encryption_key: bytes, for_model: bool = False
):
    medperf_config.ui.text = "Publishing the encryption key and the access policy"
    AssetPolicyManager(cc_config, for_model=for_model).setup_policy(
        cc_policy, encryption_key
    )


def __store_asset(cc_config: dict, asset_path: str, encryption_key: bytes):
    medperf_config.ui.text = "Encrypting asset locally"
    encrypted_asset_path = __encrypt_asset(asset_path, encryption_key)

    medperf_config.ui.text = "Uploading Encrypted asset to GCP bucket"
    asset_storage_manager = AssetStorageManager(cc_config)
    with open(encrypted_asset_path, "rb") as in_file:
        with __upload_progress(in_file) as file_obj:
            asset_storage_manager.store_asset(file_obj)
    remove_path(encrypted_asset_path)


def __encrypt_asset(asset_path: str, encryption_key: bytes) -> str:
    encrypted_asset_path = generate_tmp_path()
    encryption_key_file = tmp_path_for_cc_asset_key()
    secure_write_to_file(encryption_key_file, encryption_key)
    SymmetricEncryption().encrypt_file(
        asset_path, encryption_key_file, encrypted_asset_path
    )
    remove_path(encryption_key_file, sensitive=True)
    return encrypted_asset_path


def __upload_progress(in_file):
    """Wraps a file so that reading it reports progress through the UI."""
    return tqdm.wrapattr(
        in_file,
        "read",
        total=get_file_size(in_file),
        miniters=1,
        desc="Uploading encrypted asset to the bucket",
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        file=UIWriter(),
    )


class UIWriter:
    """A file-like object that lets tqdm write through config.ui"""

    def write(self, msg):
        medperf_config.ui.print(msg)

    def flush(self):
        pass


def get_file_size(file_object) -> int:
    """Get the size of a file in bytes."""
    try:
        total_bytes = os.fstat(file_object.fileno()).st_size
    except (AttributeError, OSError):
        total_bytes = None
    return total_bytes
