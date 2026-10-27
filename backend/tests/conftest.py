"""Общие фикстуры клиента API и изолированного приёма заявок."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def configured_signup_service(settings):
    """Изолировать лимиты и включить приём заявок на время теста."""
    settings.PUBLIC_SIGNUPS_ENABLED = True
    settings.PRIVACY_POLICY_VERSION = "test-v1"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "beta-signups-tests",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    """Создать клиент для JSON-запросов к API без авторизации."""
    return APIClient()


@pytest.fixture
def signup_payload():
    """Вернуть корректную заявку с явным согласием и пустой ловушкой."""
    return {"email": "stargazer@example.com", "consent": True, "website": ""}
