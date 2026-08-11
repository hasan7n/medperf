"""Reading what the mock backends left in a directory on this machine.

The workload side of `medperf_cc`'s mock backends: the same files, in the same
places. Nothing is attested here because nothing was protected -- selecting
`mock` on the other side already said so.
"""

import os
import shutil

ASSET_FILE = "asset.enc"
KEY_FILE = "key.bin"
RESULTS_FILE = "results.enc"
RESULTS_KEY_FILE = "results_key.enc"


def asset_directory(root: str, name: str) -> str:
    return os.path.join(root, name)


class MockStorage:
    def __init__(self, storage_config_dict: dict):
        self.directory = asset_directory(
            storage_config_dict["root"], storage_config_dict["asset_name"]
        )

    def initialize(self) -> None:
        pass

    def get_asset(self, output_path: str) -> None:
        shutil.copyfile(os.path.join(self.directory, ASSET_FILE), output_path)


class MockVault:
    def __init__(self, vault_config_dict: dict):
        self.directory = asset_directory(
            vault_config_dict["root"], vault_config_dict["asset_name"]
        )

    def initialize(self) -> None:
        pass

    def get_key(self, output_path: str) -> None:
        shutil.copyfile(os.path.join(self.directory, KEY_FILE), output_path)


class MockResult:
    def __init__(self, result_config_dict: dict):
        self.directory = asset_directory(
            result_config_dict["root"], result_config_dict["results_name"]
        )

    def initialize(self) -> None:
        os.makedirs(self.directory, exist_ok=True)

    def write_result(self, result_path: str) -> None:
        shutil.copyfile(result_path, os.path.join(self.directory, RESULTS_FILE))

    def write_key(self, key_bytes: bytes) -> None:
        with open(os.path.join(self.directory, RESULTS_KEY_FILE), "wb") as f:
            f.write(key_bytes)

    def do_test(self, test_data: bytes) -> None:
        """Proves the workload can write where the operator will look, before
        spending the run finding out that it cannot."""
        os.makedirs(self.directory, exist_ok=True)
        probe = os.path.join(self.directory, "write_probe")
        with open(probe, "wb") as f:
            f.write(test_data)
        os.remove(probe)
