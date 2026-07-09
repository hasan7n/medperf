from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


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
