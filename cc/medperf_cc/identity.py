"""What a confidential workload is, and which parts of it an asset owner pins.

A workload's identity is a `::`-joined string of hashes in one fixed order.
Both sides of an authorization derive it from the same ordered list of terms:
the asset owner when they say who may decrypt, and whoever checks an
attestation against that. If the two ever disagreed about which term is which,
nothing would error -- every authorization would silently stop matching.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

SCRIPT_TERM = "script"
DATA_TERM = "data"
MODEL_TERM = "model"
COLLECTOR_TERM = "collector"

# The order is what makes two identity strings comparable at all.
TERM_ORDER = [SCRIPT_TERM, DATA_TERM, MODEL_TERM, COLLECTOR_TERM]

# Where each term is found in a Confidential Space attestation. These are token
# claim paths, which every key release backend reads one way or another: one
# has the cloud evaluate them, another looks them up in the token itself.
TERM_CLAIMS = {
    SCRIPT_TERM: "submods.container.image_digest",
    DATA_TERM: "submods.container.env_override.EXPECTED_DATA_HASH",
    MODEL_TERM: "submods.container.env_override.EXPECTED_MODEL_HASH",
    COLLECTOR_TERM: "submods.container.env_override.EXPECTED_RESULT_COLLECTOR_HASH",
}

# The field of a `WorkloadIdentity` each term is taken from.
TERM_FIELDS = {
    SCRIPT_TERM: "script_hash",
    DATA_TERM: "data_hash",
    MODEL_TERM: "model_hash",
    COLLECTOR_TERM: "result_collector_hash",
}


class AssetKind(Enum):
    DATA = "data"
    MODEL = "model"

    @property
    def own_term(self) -> str:
        return DATA_TERM if self is AssetKind.DATA else MODEL_TERM

    @property
    def peer_term(self) -> str:
        return MODEL_TERM if self is AssetKind.DATA else DATA_TERM


class WorkloadIdentity(BaseModel):
    """The hashes a workload attests with, plus ids used for storage paths.

    Only the `*_hash` fields ever take part in an identity. The `*_id` fields
    build a readable storage prefix and are never attested, so nothing that
    matters may depend on them.
    """

    script_hash: str
    script_id: int
    model_hash: str = ""
    model_id: Optional[int] = None
    data_hash: str = ""
    data_id: Optional[int] = None
    result_collector_hash: str = ""
    execution_id: Optional[int] = None

    @property
    def storage_prefix(self) -> str:
        prefix = f"d{self.data_id}-m{self.model_id}-s{self.script_id}"
        if self.execution_id:
            return f"{prefix}-e{self.execution_id}"
        return prefix

    @property
    def results_path(self) -> str:
        return f"{self.storage_prefix}/output"

    @property
    def results_encryption_key_path(self) -> str:
        return f"{self.storage_prefix}/encryption_key"


class WorkloadBinding(BaseModel):
    """The terms one asset owner pins, in canonical order.

    Built from an `AssetPolicy`, which is what decides how many of them there
    are; the order they come in is fixed here."""

    terms: List[str]

    def binds(self, term: str) -> bool:
        return term in self.terms

    def identity_of(self, workload: WorkloadIdentity) -> str:
        return "::".join(getattr(workload, TERM_FIELDS[term]) for term in self.terms)
