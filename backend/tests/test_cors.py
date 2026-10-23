import pytest

from beta.models import BetaSignup

pytestmark = pytest.mark.django_db

SIGNUPS_URL = "/api/v1/beta-signups/"
FRONTEND_ORIGIN = "https://frontend.example"


@pytest.fixture(autouse=True)
def allowed_frontend_origin(settings):
    settings.CORS_ALLOWED_ORIGINS = [FRONTEND_ORIGIN]


def test_allowed_frontend_can_preflight_a_json_signup(api_client):
    response = api_client.options(
        SIGNUPS_URL,
        HTTP_ORIGIN=FRONTEND_ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
    )

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
    assert "POST" in response["Access-Control-Allow-Methods"].split(", ")
    assert "content-type" in response["Access-Control-Allow-Headers"].lower().split(", ")
    assert "Access-Control-Allow-Credentials" not in response
    assert "origin" in response["Vary"].lower()
    assert not BetaSignup.objects.exists()


@pytest.mark.parametrize(
    "origin",
    [
        "https://other.example",
        "https://frontend.example.attacker.example",
        "http://frontend.example",
        "https://frontend.example:444",
    ],
)
def test_preflight_allows_only_exact_origin_including_scheme_and_port(api_client, origin):
    response = api_client.options(
        SIGNUPS_URL,
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
    )

    assert "Access-Control-Allow-Origin" not in response
    assert "Access-Control-Allow-Credentials" not in response
    assert not BetaSignup.objects.exists()


def test_frontend_can_read_signup_receipt_and_retry_after(api_client, signup_payload):
    for _ in range(5):
        response = api_client.post(
            SIGNUPS_URL, signup_payload, format="json", HTTP_ORIGIN=FRONTEND_ORIGIN
        )
        assert response.status_code == 202
        assert response["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN

    response = api_client.post(
        SIGNUPS_URL, signup_payload, format="json", HTTP_ORIGIN=FRONTEND_ORIGIN
    )

    assert response.status_code == 429
    assert response["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
    assert "retry-after" in response["Access-Control-Expose-Headers"].lower().split(", ")
    assert int(response["Retry-After"]) > 0
    assert "Access-Control-Allow-Credentials" not in response
