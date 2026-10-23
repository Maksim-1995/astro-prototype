import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def configured_signup_service(settings):
    """Isolate request limits and opt into collecting data only inside tests."""
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
    return APIClient()


@pytest.fixture
def signup_payload():
    return {"email": "stargazer@example.com", "consent": True, "website": ""}
