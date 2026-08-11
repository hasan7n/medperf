"""What an asset owner requires of a confidential workload.

Stated in terms of the workload, never of a particular cloud: each key release
backend translates this into whatever it enforces policy with.
"""

from typing import Optional

from pydantic import BaseModel


class AssetPolicy(BaseModel):
    """Where a workload must run before this asset's key is released to it.

    Both are optional, and an unset one is not checked at all.
    """

    # The cloud region or zone the confidential VM must be running in.
    location: Optional[str] = None
    # The confidential hardware platform, as the attestation reports it.
    hardware: Optional[str] = None

    class Config:
        # A policy decides who may read an asset. A key the owner misspelled is
        # a policy they did not get, so it is refused rather than ignored.
        extra = "forbid"
