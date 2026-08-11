"""What the broker will release a key for.

Deliberately the same policy MedPerf writes to Google Cloud. There, an asset
owner installs an attribute mapping on a workload identity pool and binds IAM
principals matching it; here the broker evaluates the same terms against the
same claims itself. The identity strings are byte for byte the ones
`WorkloadBinding` produces, so an asset can move between backends without its
owner restating what they meant.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, validator

from medperf_cc.attestation import (
    AttestationRequirements,
    AttestationToken,
    TokenType,
    TrustAnchor,
)
from medperf_cc.errors import AttestationError
from medperf_cc.identity import TERM_ORDER, WorkloadBinding


class AttestationPolicy(BaseModel):
    """The environment an asset owner requires of a workload."""

    audience: str
    allowed_token_types: List[str] = ["PKI"]
    require_confidential_space: bool = True
    require_stable_image: bool = True
    allow_debug: bool = False
    zone: Optional[str] = None
    hardware_model: Optional[str] = None

    def requirements(self, nonce: str) -> AttestationRequirements:
        return AttestationRequirements(
            audience=self.audience,
            nonce=nonce,
            allowed_token_types=[TokenType(t) for t in self.allowed_token_types],
            require_confidential_space=self.require_confidential_space,
            require_stable_image=self.require_stable_image,
            allow_debug=self.allow_debug,
            zone=self.zone,
            hardware_model=self.hardware_model,
        )


class AssetPolicy(BaseModel):
    """One asset's policy: which identities may have its key, and from where."""

    terms: List[str] = Field(..., min_items=1)
    permitted_identities: List[str] = []
    attestation: AttestationPolicy

    @validator("terms")
    def canonical_terms(cls, terms):
        """The order is what makes two identity strings comparable at all."""
        unknown = set(terms) - set(TERM_ORDER)
        if unknown:
            raise ValueError(f"Unknown workload identity terms: {sorted(unknown)}")
        if terms != [term for term in TERM_ORDER if term in terms]:
            raise ValueError("Workload identity terms are not in canonical order")
        return terms

    @property
    def binding(self) -> WorkloadBinding:
        return WorkloadBinding(terms=self.terms)

    def authorize(
        self, token: AttestationToken, anchor: TrustAnchor, nonce: str
    ) -> str:
        """Verifies a token and checks the identity it presents.

        Returns the matched identity, and raises `AttestationError` otherwise.
        The caller must not tell a client which of the two it was."""
        anchor.verify_signature(token)
        self.attestation.requirements(nonce).check(token)

        identity = self.binding.identity_from_claims(token.claims)
        if identity not in self.permitted_identities:
            raise AttestationError(
                f"Workload identity {identity!r} is not permitted for this asset"
            )
        return identity
