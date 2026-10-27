"""Проверки обработки дубликатов и ошибок сохранения заявок."""

import pytest
from beta.models import BetaSignup
from beta.services import register_signup
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def test_duplicate_insert_keeps_enclosing_transaction_usable():
    """Сохранить внешнюю транзакцию после вставки дубликата."""
    register_signup(email="stargazer@example.com")
    signup = BetaSignup.objects.get()
    signup.status = BetaSignup.Status.INVITED
    signup.save(update_fields=["status"])

    with transaction.atomic():
        register_signup(email="STARGAZER@example.com")
        assert BetaSignup.objects.count() == 1

    signup.refresh_from_db()
    assert signup.status == BetaSignup.Status.INVITED


def test_unrelated_integrity_error_is_not_misreported_as_a_duplicate(
    monkeypatch,
):
    """Не скрывать постороннюю ошибку целостности при вставке."""

    def failing_create(**kwargs):
        """Подменить создание заявки посторонней ошибкой целостности."""
        raise IntegrityError("unrelated insert failure")

    monkeypatch.setattr(BetaSignup.objects, "create", failing_create)

    with pytest.raises(IntegrityError, match="unrelated insert failure"):
        register_signup(email="stargazer@example.com")

    assert not BetaSignup.objects.exists()
