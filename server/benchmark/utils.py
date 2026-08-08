from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

# Each topology fixes three things: the kind of model it runs, whether it needs
# a separate evaluator container, and whether it needs a benchmark script (the
# benchmark-owned container that loads an asset model).
TOPOLOGY_RULES = {
    "byo_inference_script": {
        "model_type": "CONTAINER",
        "data_evaluator_mlcube": True,
        "benchmark_script": False,
    },
    "end_to_end_script": {
        "model_type": "ASSET",
        "data_evaluator_mlcube": False,
        "benchmark_script": True,
    },
    "inference_script": {
        "model_type": "ASSET",
        "data_evaluator_mlcube": True,
        "benchmark_script": True,
    },
}


def expected_model_type(topology):
    """The kind of model a topology's reference and associated models must be."""
    return TOPOLOGY_RULES[topology]["model_type"]


def validate_topology(topology, reference_model, data_evaluator_mlcube, benchmark_script):
    """Ensures a benchmark's components match what its topology calls for.

    Raises `serializers.ValidationError` on any mismatch."""
    rules = TOPOLOGY_RULES.get(topology)
    if rules is None:
        raise serializers.ValidationError(
            {"topology": f"Unknown benchmark topology: {topology}"}
        )

    components = {
        "data_evaluator_mlcube": data_evaluator_mlcube,
        "benchmark_script": benchmark_script,
    }
    for field, value in components.items():
        if rules[field] and value is None:
            raise serializers.ValidationError(
                {field: f"A {topology} benchmark must define a {field}"}
            )
        if not rules[field] and value is not None:
            raise serializers.ValidationError(
                {field: f"A {topology} benchmark must not define a {field}"}
            )

    if reference_model is not None and reference_model.type != rules["model_type"]:
        raise serializers.ValidationError(
            {
                "reference_model": (
                    f"A {topology} benchmark requires a {rules['model_type']}"
                    f" reference model, but the given model is a"
                    f" {reference_model.type}"
                )
            }
        )


def resolve_committee_member_emails(emails, owner=None):
    normalized_emails = list(
        dict.fromkeys(
            email.lower().strip() for email in emails if email and str(email).strip()
        )
    )
    users = []
    missing_emails = []
    for email in normalized_emails:
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            missing_emails.append(email)
            continue
        if owner is not None and user.id == owner.id:
            raise serializers.ValidationError(
                {
                    "committee_member_emails": (
                        "Benchmark owner cannot be a committee member"
                    )
                }
            )
        users.append(user)
    if missing_emails:
        raise serializers.ValidationError(
            {"committee_member_emails": f"Users not found: {missing_emails}"}
        )
    return users
