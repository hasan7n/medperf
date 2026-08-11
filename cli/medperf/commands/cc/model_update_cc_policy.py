from medperf import config
from medperf.account_management.account_management import get_medperf_user_object
from medperf.cc.assets import set_permitted_workloads, sync_cc_metadata
from medperf.cc.workloads import get_associated_benchmarks, get_confidential_plan
from medperf.entities.model import Model
from medperf.exceptions import MedperfException
from medperf_cc.identity import AssetKind, WorkloadIdentity


def get_permitted_workloads(model: Model):
    """The workloads a model owner authorizes to load their weights.

    A model-side grant pins only the benchmark script and the model, so it does
    not name datasets or result collectors: it says "this image may load my
    weights", and leaves it to each data owner's own policy to decide which
    data that image is allowed to see."""
    user_obj = get_medperf_user_object()
    if model.owner != user_obj.id:
        raise MedperfException("User must be model owner")
    asset = model.asset_obj

    permitted_workloads = []
    for benchmark in get_associated_benchmarks(model.id, "model"):
        plan = get_confidential_plan(benchmark)
        if plan is None:
            continue
        permitted_workloads.append(
            WorkloadIdentity(
                model_hash=asset.asset_hash,
                script_hash=plan.script_hash,
                model_id=model.id,
                script_id=plan.script_id,
            )
        )

    return permitted_workloads


class ModelUpdateCCPolicy:
    @classmethod
    def run(cls, model_uid: int):
        model = Model.get(model_uid)
        if not model.is_cc_configured():
            raise MedperfException(
                f"Model {model.id} is not configured for confidential computing."
            )
        with config.ui.interactive():
            config.ui.text = "Updating model confidential computing policy"
            permitted_workloads = get_permitted_workloads(model)
            set_permitted_workloads(model, AssetKind.MODEL, permitted_workloads)
            sync_cc_metadata(model, config.comms.update_model)
