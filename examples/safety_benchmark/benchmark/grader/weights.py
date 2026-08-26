"""The grader's weights: where they come from, and what they must hash to.

Nothing here is configurable. The weights, the revision they are pinned to and
the Llama Guard version whose prompt format they expect travel together: a run
cannot pair one version's weights with another's format, and cannot be pointed
at weights nobody vouched for.
"""

import hashlib
import os

import requests

REPO = "llamas-community/LlamaGuard-7b"
REVISION = "6efebd6fbad466480971c69d9a5a52f8a7dd87af"
VERSION = "1"

BASE_URL = f"https://huggingface.co/{REPO}/resolve/{REVISION}"
DIRECTORY = os.path.join(os.environ.get("TMP_FILES", "/tmp"), "grader_weights")

FILES = {
    "config.json": "35ec40685a6669878e5d98335192437b4b401ced8aec7e9274b04d812c9b4654",
    "generation_config.json": "14ac5e45a47a9c4e1c5a28a0d41d9cc7a8d9f3e25caf709f8936549dafa6586a",
    "model-00001-of-00003.safetensors": "f9e6f2ab03a3b92bf4bc6cfd6d6dcdaa8b36ab5ecf73dcfd1e8da3b5a95261a8",
    "model-00002-of-00003.safetensors": "4d92c8b74f78b0e0f4b32921d13a007efcd0e0447290da6d92f787c3295b0ad8",
    "model-00003-of-00003.safetensors": "a19b92a679870c311122d67ae980737cf3e51424b396b3809463c4d9b06c7fcf",
    "model.safetensors.index.json": "0e3aa3ec6e7d38edaacc0d9c5fe74d33b16699a6a14f6f0711365b64388ff7ab",
    "special_tokens_map.json": "6fa06efa2785e450051989a6f8fb4416b10149ded485ddd3f127a40734f5cfd0",
    "tokenizer.json": "bcd04f0eadf90287bd26e1a183ac487d8a141b09b06aecb7725bbdd343640f2e",
    "tokenizer.model": "9e556afd44213b6bd1be2b850ebbbd98f5481437a8021afaf58ee7fb1818d347",
    "tokenizer_config.json": "adf699562612cb05c618056c29641916f808c70755e2ad4a37080a479b44ede2",
    "LICENSE.txt": "41774062cd349c744e8ee986c1aaf5784b7e42fbe306619536fa7386d421da78",
    "USE_POLICY.md": "c532a41537ad260e9d29eb5e2c0f18c4d3e6aff7f571e4aaf2284cbd7b079fe4",
}

CHUNK_BYTES = 1 << 20
DOWNLOAD_TIMEOUT_SECONDS = 60


def ensure() -> str:
    os.makedirs(DIRECTORY, exist_ok=True)
    for name, expected in FILES.items():
        path = os.path.join(DIRECTORY, name)
        if os.path.exists(path) and file_hash(path) == expected:
            continue
        download(name, path, expected)
    return DIRECTORY


def download(name: str, path: str, expected: str) -> None:
    with requests.get(
        f"{BASE_URL}/{name}", stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS
    ) as response:
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(CHUNK_BYTES):
                f.write(chunk)

    actual = file_hash(path)
    if actual != expected:
        os.remove(path)
        raise ValueError(f"{name}: expected sha256 {expected}, got {actual}")


def file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()
