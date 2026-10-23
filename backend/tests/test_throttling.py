import pytest
from django.core.cache import caches
from django.core.cache.backends.db import DatabaseCache
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from beta.models import BetaSignup

SIGNUPS_URL = "/api/v1/beta-signups/"


@pytest.mark.django_db
def test_burst_limit_blocks_sixth_request(api_client, signup_payload):
    for _ in range(5):
        assert api_client.post(SIGNUPS_URL, signup_payload, format="json").status_code == 202

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0
    assert BetaSignup.objects.count() == 1


@pytest.mark.django_db
def test_daily_limit_survives_burst_window_resets(api_client, signup_payload, monkeypatch):
    current_time = [1_700_000_000.0]
    monkeypatch.setattr(SimpleRateThrottle, "timer", lambda self: current_time[0])
    for _ in range(30):
        assert api_client.post(SIGNUPS_URL, signup_payload, format="json").status_code == 202
        current_time[0] += 61

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 429
    assert int(response["Retry-After"]) > 60
    assert BetaSignup.objects.count() == 1


@pytest.mark.django_db
def test_one_trusted_proxy_uses_rightmost_forwarded_ip_despite_spoofed_prefix(
    api_client, signup_payload
):
    # Production Nginx replaces X-Forwarded-For with the connection address.
    # This also verifies DRF's NUM_PROXIES=1 interpretation if a chain arrives:
    # a changing attacker-controlled prefix must not create new throttle buckets.
    for index in range(5):
        response = api_client.post(
            SIGNUPS_URL,
            signup_payload,
            format="json",
            REMOTE_ADDR="192.0.2.10",
            HTTP_X_FORWARDED_FOR=f"198.51.100.{index + 1}, 203.0.113.20",
        )
        assert response.status_code == 202

    blocked_response = api_client.post(
        SIGNUPS_URL,
        signup_payload,
        format="json",
        REMOTE_ADDR="192.0.2.10",
        HTTP_X_FORWARDED_FOR="198.51.100.99, 203.0.113.20",
    )
    different_visitor_response = api_client.post(
        SIGNUPS_URL,
        signup_payload,
        format="json",
        REMOTE_ADDR="192.0.2.10",
        HTTP_X_FORWARDED_FOR="203.0.113.21",
    )

    assert blocked_response.status_code == 429
    assert different_visitor_response.status_code == 202


@pytest.mark.django_db(transaction=True)
def test_database_cache_shares_limits_between_independent_clients(settings, signup_payload):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "astro_throttle_test_cache",
        }
    }
    call_command("createcachetable", "astro_throttle_test_cache", verbosity=0)
    assert isinstance(caches["default"], DatabaseCache)
    first_client = APIClient()
    second_client = APIClient()
    for _ in range(5):
        assert first_client.post(SIGNUPS_URL, signup_payload, format="json").status_code == 202

    response = second_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 429
    assert BetaSignup.objects.count() == 1
