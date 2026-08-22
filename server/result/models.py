from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ModelResult(models.Model):
    MODEL_RESULT_STATUS = (
        ("PENDING", "PENDING"),
        ("APPROVED", "APPROVED"),
        ("REJECTED", "REJECTED"),
    )

    name = models.CharField(max_length=128, blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    benchmark = models.ForeignKey("benchmark.Benchmark", on_delete=models.CASCADE)
    model = models.ForeignKey("model.Model", on_delete=models.PROTECT)
    dataset = models.ForeignKey("dataset.Dataset", on_delete=models.PROTECT)
    results = models.JSONField(default=dict)
    finalized = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict)
    user_metadata = models.JSONField(default=dict)
    approval_status = models.CharField(
        choices=MODEL_RESULT_STATUS, max_length=100, default="PENDING"
    )
    is_valid = models.BooleanField(default=True)
    model_report = models.JSONField(default=dict, blank=True, null=True)
    # What a confidential workload attested about these results. A dedicated
    # field rather than a corner of `metadata`, so an execution without one is
    # visibly unverified rather than quietly indistinguishable.
    integrity_proof = models.JSONField(default=dict, blank=True, null=True)
    # Whoever the results were encrypted for, when that is not the operator.
    # Both asset owners' policies name a role and the client resolves it to one
    # party before launching; recording it here is what lets that party read
    # and report an execution they did not create. Null for everything else.
    result_collector = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="collected_results",
    )
    evaluation_report = models.JSONField(default=dict, blank=True, null=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["modified_at"]
