"""Picking up what a confidential workload left, and opening it.

Decryption happens here rather than inside `medperf_cc` for the same reason
encryption does: the private key that opens the results belongs to the client,
and reaching the store needs credentials that never leave the machine holding
them.
"""

import medperf.config as medperf_config
from medperf.cc.config import result_store_for
from medperf.cc.errors import as_medperf_error
from medperf.encryption import AsymmetricEncryption, SymmetricEncryption
from medperf.entities.user import User
from medperf.exceptions import ExecutionError
from medperf.utils import (
    generate_tmp_path,
    remove_path,
    secure_write_to_file,
    tmp_path_for_cc_asset_key,
    untar,
)
from medperf_cc import ResultStore, WorkloadIdentity


@as_medperf_error()
def setup_collector(user: User):
    """Checks this user can actually receive results where they said.

    The mirror of `setup_operator`: whoever runs the workload needs a machine,
    whoever the results are for needs somewhere to receive them."""
    if not user.cc_collector.configured:
        return

    result_store_for(user.cc_collector.config).verify()


@as_medperf_error(ExecutionError)
def results_exist(result_store: ResultStore, workload: WorkloadIdentity) -> bool:
    return result_store.results_ready(workload)


@as_medperf_error(ExecutionError)
def fetch_results(
    result_store: ResultStore,
    workload: WorkloadIdentity,
    private_key_bytes: bytes,
    results_path: str,
) -> None:
    """Downloads one workload's output and unpacks it, as files."""
    encrypted_results_path = generate_tmp_path()
    encrypted_key = result_store.fetch(workload, encrypted_results_path)

    medperf_config.ui.text = "Decrypting results"
    decryption_key = AsymmetricEncryption().decrypt(private_key_bytes, encrypted_key)

    results_archive_path = generate_tmp_path()
    tmp_key_path = tmp_path_for_cc_asset_key()
    secure_write_to_file(tmp_key_path, decryption_key)
    SymmetricEncryption().decrypt_file(
        encrypted_results_path, tmp_key_path, results_archive_path
    )
    remove_path(tmp_key_path, sensitive=True)
    del decryption_key

    medperf_config.ui.text = "Uncompressing results"
    untar(results_archive_path, remove=True, extract_to=results_path)
