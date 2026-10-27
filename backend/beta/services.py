"""Создание заявок и обработка повторной отправки."""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import BetaSignup


def register_signup(*, email):
    """Сохраняет новую заявку, не обновляя согласие и статус дубликата.

    Вложенная транзакция позволяет обработать конфликт уникальности,
    сохранив работоспособность вызывающей транзакции.
    """
    email = email.strip().lower()
    try:
        with transaction.atomic():
            BetaSignup.objects.create(
                email=email,
                consented_at=timezone.now(),
                privacy_policy_version=settings.PRIVACY_POLICY_VERSION,
            )
    except IntegrityError:
        # Обрабатываем дубли, в том числе при одновременной отправке.
        # Другие ошибки должны попасть к вызывающему коду.
        if not BetaSignup.objects.filter(email__iexact=email).exists():
            raise
