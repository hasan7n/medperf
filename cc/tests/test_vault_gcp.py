"""The one place where a binding is written twice.

A workload identity pool is told how to *build* an identity out of attestation
assertions; the key is bound to the identities the owner *permits*. If those two
ever described different terms, nothing would error -- every authorization would
silently stop matching.
"""

import pytest

from medperf_cc.vault.gcp import workload_uid_assertion
from medperf_cc.identity import TERM_CLAIMS, AssetKind, WorkloadIdentity
from tests.conftest import any_policy


@pytest.mark.parametrize("kind", [AssetKind.DATA, AssetKind.MODEL])
def test_the_assertion_and_the_identity_have_the_same_shape(kind):
    binding = any_policy().binding(kind)
    workload = WorkloadIdentity(
        script_hash="s",
        data_hash="d",
        model_hash="m",
        result_collector_hash="c",
        script_id=1,
    )

    assertion = workload_uid_assertion(binding)

    assert assertion.count('+"::"+') == binding.identity_of(workload).count("::")


def test_the_assertion_reads_the_terms_in_binding_order():
    binding = any_policy().binding(AssetKind.DATA)

    assertion = workload_uid_assertion(binding)

    assert assertion.split('+"::"+') == [
        f"assertion.{TERM_CLAIMS[term]}" for term in binding.terms
    ]
