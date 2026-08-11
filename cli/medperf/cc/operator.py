"""Operating a confidential workload: start it, watch it, collect its output.

Decryption happens here rather than inside `medperf_cc`, for the same reason
encryption does: the private key that opens the results belongs to the client.
"""

from colorama import Fore, Style

import medperf.config as medperf_config
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
from medperf_cc.cc_operator import OperatorManager
from medperf_cc.gcp import CCWorkloadID


@as_medperf_error()
def setup_operator(user: User):
    if not user.is_cc_configured():
        return

    cc_config = user.get_cc_config()
    operator_manager = OperatorManager(cc_config)
    operator_manager.setup()


@as_medperf_error(ExecutionError)
def run_workload(
    docker_image: str,
    workload: CCWorkloadID,
    dataset_cc_config: dict,
    model_cc_config: dict,
    operator_cc_config: dict,
    result_collector_public_key: str,
):

    operator_manager = OperatorManager(operator_cc_config)
    operator_manager.run_workload(
        docker_image,
        workload,
        dataset_cc_config,
        model_cc_config,
        result_collector_public_key,
    )


@as_medperf_error(ExecutionError)
def wait_for_workload(workload: CCWorkloadID, operator_cc_config: dict):
    operator_manager = OperatorManager(operator_cc_config)
    for output in operator_manager.wait_for_workload_completion(workload):
        medperf_config.ui.print_subprocess_logs(
            f"{Fore.WHITE}{Style.DIM}{output}{Style.RESET_ALL}"
        )


@as_medperf_error(ExecutionError)
def workload_results_exists(operator_cc_config: dict, workload: CCWorkloadID) -> bool:
    operator_manager = OperatorManager(operator_cc_config)
    return operator_manager.results_exist(workload)


@as_medperf_error(ExecutionError)
def download_results(
    operator_cc_config: dict,
    workload: CCWorkloadID,
    private_key_bytes: bytes,
    results_path: str,
):
    operator_manager = OperatorManager(operator_cc_config)

    encrypted_results_path = generate_tmp_path()
    encrypted_key = operator_manager.download_results(workload, encrypted_results_path)

    medperf_config.ui.text = "Decrypting predictions"

    decryption_key = AsymmetricEncryption().decrypt(private_key_bytes, encrypted_key)

    results_archive_path = generate_tmp_path()
    tmp_key_path = tmp_path_for_cc_asset_key()
    secure_write_to_file(tmp_key_path, decryption_key)
    SymmetricEncryption().decrypt_file(
        encrypted_results_path, tmp_key_path, results_archive_path
    )
    remove_path(tmp_key_path, sensitive=True)
    del decryption_key

    # Extract results
    medperf_config.ui.text = "Uncompressing predictions"
    untar(results_archive_path, remove=True, extract_to=results_path)
