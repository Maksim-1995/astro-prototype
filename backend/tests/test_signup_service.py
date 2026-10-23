import pytest
from django.db import IntegrityError, transaction

from beta.models import BetaSignup
from beta.services import register_signup

pytestmark = pytest.mark.django_db


def test_duplicate_insert_keeps_enclosing_transaction_usable():
    register_signup(email="stargazer@example.com")
    signup = BetaSignup.objects.get()
    signup.status = BetaSignup.Status.INVITED
    signup.save(update_fields=["status"])

    with transaction.atomic():
        register_signup(email="STARGAZER@example.com")
        assert BetaSignup.objects.count() == 1

    signup.refresh_from_db()
    assert signup.status == BetaSignup.Status.INVITED


def test_unrelated_integrity_error_is_not_misreported_as_a_duplicate(monkeypatch):
    def failing_create(**kwargs):
        raise IntegrityError("unrelated insert failure")

    monkeypatch.setattr(BetaSignup.objects, "create", failing_create)

    with pytest.raises(IntegrityError, match="unrelated insert failure"):
        register_signup(email="stargazer@example.com")

    assert not BetaSignup.objects.exists()
