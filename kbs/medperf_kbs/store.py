"""On-disk store for assets, their keys and their policies.

A directory per asset. Deliberately boring: the security of a key broker comes
from the release path being right, not from the storage being clever.
"""

import json
import os
import shutil
import stat
from dataclasses import dataclass
from typing import List, Optional

from medperf_kbs.policy import AssetPolicy

POLICY_FILE = "policy.json"
KEY_FILE = "key.bin"
BLOB_FILE = "asset.enc"


class AssetNotFound(Exception):
    pass


@dataclass
class AssetStore:
    root: str

    def exists(self, asset_id: str) -> bool:
        return os.path.isdir(self.__asset_dir(asset_id))

    def list_assets(self) -> List[str]:
        if not os.path.isdir(self.root):
            return []
        return sorted(
            name
            for name in os.listdir(self.root)
            if os.path.isdir(os.path.join(self.root, name))
        )

    def put_policy(self, asset_id: str, policy: AssetPolicy):
        directory = self.__asset_dir(asset_id)
        os.makedirs(directory, exist_ok=True)
        self.__write_private(
            os.path.join(directory, POLICY_FILE), policy.json(indent=2).encode()
        )

    def put_key(self, asset_id: str, key: bytes):
        directory = self.__asset_dir(asset_id)
        os.makedirs(directory, exist_ok=True)
        self.__write_private(os.path.join(directory, KEY_FILE), key)

    def put_blob(self, asset_id: str, source_path: str):
        directory = self.__asset_dir(asset_id)
        os.makedirs(directory, exist_ok=True)
        shutil.move(source_path, os.path.join(directory, BLOB_FILE))

    def delete(self, asset_id: str):
        directory = self.__asset_dir(asset_id)
        if os.path.isdir(directory):
            shutil.rmtree(directory)

    def get_policy(self, asset_id: str) -> AssetPolicy:
        path = os.path.join(self.__asset_dir(asset_id), POLICY_FILE)
        if not os.path.exists(path):
            raise AssetNotFound(asset_id)
        with open(path) as f:
            return AssetPolicy(**json.load(f))

    def get_key(self, asset_id: str) -> bytes:
        path = os.path.join(self.__asset_dir(asset_id), KEY_FILE)
        if not os.path.exists(path):
            raise AssetNotFound(asset_id)
        with open(path, "rb") as f:
            return f.read()

    def blob_path(self, asset_id: str) -> Optional[str]:
        path = os.path.join(self.__asset_dir(asset_id), BLOB_FILE)
        return path if os.path.exists(path) else None

    def __asset_dir(self, asset_id: str) -> str:
        # Asset ids arrive over the network, so keep them to one path segment.
        if (
            not asset_id
            or "/" in asset_id
            or "\\" in asset_id
            or asset_id.startswith(".")
        ):
            raise ValueError(f"Invalid asset id: {asset_id!r}")
        return os.path.join(self.root, asset_id)

    @staticmethod
    def __write_private(path: str, content: bytes):
        # Opened 0600 rather than chmod'ed afterwards, so the content is never
        # briefly world readable.
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR
        )
        with os.fdopen(descriptor, "wb") as f:
            f.write(content)
