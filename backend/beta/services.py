from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import BetaSignup


def register_signup(*, email):
    """Store one contact. Repeating a submission preserves its original consent and status."""
    email = email.strip().lower()
    try:
        with transaction.atomic():
            BetaSignup.objects.create(
                email=email,
                consented_at=timezone.now(),
                privacy_policy_version=settings.PRIVACY_POLICY_VERSION,
            )
    except IntegrityError:
        # Handle concurrent duplicates without hiding unrelated integrity failures.
        if not BetaSignup.objects.filter(email__iexact=email).exists():
            raise
