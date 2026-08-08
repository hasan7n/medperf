from medperf import config
from medperf.account_management.account_management import get_medperf_user_object
from medperf.asset_management.asset_management import update_dataset_cc_policy
from medperf.asset_management.gcp_utils import CCWorkloadID
from medperf.commands.cc.utils import (
    dedup_workloads,
    get_approved_component_ids,
    get_associated_benchmarks,
    get_confidential_plan,
    public_key_hash,
    sync_cc_metadata,
)
from medperf.commands.certificate.utils import current_user_certificate_status
from medperf.entities.certificate import Certificate
from medperf.entities.dataset import Dataset
from medperf.entities.model import Model
from medperf.enums import CryptoKeyType
from medperf.exceptions import MedperfException


def get_permitted_workloads(dataset: Dataset):
    """The workloads a data owner authorizes to read their data.

    A data-side grant pins all four parties — script, data, model and result
    collector — so it authorizes one exact combination. The data owner is the
    gatekeeper on the data, which is why this policy, unlike the model-side one,
    enumerates the models it will run against."""
    user_obj = get_medperf_user_object()
    if dataset.owner != user_obj.id:
        raise MedperfException("User must be data owner")

    result_collector_hash = public_key_hash(_get_user_certificate())

    permitted_workloads = []
    for benchmark in get_associated_benchmarks(dataset.id, "dataset"):
        plan = get_confidential_plan(benchmark)
        if plan is None:
            continue
        for model_id in get_approved_component_ids(benchmark.id, "model"):
            model = Model.get(model_id)
            if not model.requires_cc():
                continue
            permitted_workloads.append(
                CCWorkloadID(
                    data_hash=dataset.generated_uid,
                    model_hash=model.asset_obj.asset_hash,
                    script_hash=plan.script_hash,
                    result_collector_hash=result_collector_hash,
                    data_id=dataset.id,
                    model_id=model.id,
                    script_id=plan.script_id,
                )
            )

    return dedup_workloads(permitted_workloads)


def _get_user_certificate() -> Certificate:
    status_dict = current_user_certificate_status(CryptoKeyType.RSA)
    user_cert = None
    if status_dict["should_be_submitted"]:
        user_cert = Certificate.get_local_user_certificate(CryptoKeyType.RSA)
    elif status_dict["no_action_required"]:
        user_cert = status_dict["user_cert_object"]

    if not user_cert:
        raise MedperfException("User must have a certificate to update cc policy")
    return user_cert


class DatasetUpdateCCPolicy:
    @classmethod
    def run(cls, data_uid: int):
        dataset = Dataset.get(data_uid)
        if not dataset.is_cc_configured():
            raise MedperfException(
                f"Dataset {dataset.id} is not configured for confidential computing."
            )
        with config.ui.interactive():
            config.ui.text = "Updating dataset confidential computing policy"
            permitted_workloads = get_permitted_workloads(dataset)
            update_dataset_cc_policy(dataset, permitted_workloads)
            sync_cc_metadata(dataset, config.comms.update_dataset)
