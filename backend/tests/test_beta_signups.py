"""Проверки создания заявок, согласия и защиты персональных данных."""

import pytest
from beta.models import BetaSignup
from django.db import IntegrityError, transaction
from django.utils import timezone

pytestmark = pytest.mark.django_db

SIGNUPS_URL = "/api/v1/beta-signups/"
ACCEPTED_RESPONSE = {
    "detail": "Заявка принята. Если вы ещё не в списке, мы добавим ваш email."
}


def test_accepts_signup_and_records_server_side_consent(
    api_client, signup_payload
):
    """Сохранить заявку, дату согласия и серверную версию политики."""
    before_request = timezone.now()

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 202
    assert response.json() == ACCEPTED_RESPONSE
    signup = BetaSignup.objects.get()
    assert signup.email == signup_payload["email"]
    assert signup.status == "new"
    assert signup.privacy_policy_version == "test-v1"
    assert before_request <= signup.created_at <= timezone.now()
    assert before_request <= signup.consented_at <= timezone.now()


def test_normalizes_email_before_saving(api_client, signup_payload):
    """Сохранить email без пробелов и в нижнем регистре."""
    signup_payload["email"] = "  StarGazer@EXAMPLE.COM  "

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 202
    assert BetaSignup.objects.get().email == "stargazer@example.com"


def test_email_length_is_validated_after_unicode_lowercase_expansion(
    api_client, signup_payload
):
    """Отклонить email длиннее лимита после нормализации."""
    # U+0130 в нижнем регистре превращается в две кодовые точки.
    # Исходный email проходит лимит, но после нормализации не влезает
    # в varchar(254).
    signup_payload["email"] = "İ" * 240 + "@example.com"
    assert len(signup_payload["email"]) <= 254

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 400
    assert "email" in response.json()
    assert not BetaSignup.objects.exists()


@pytest.mark.parametrize(
    "email", ["stargazer@example.com", "STARGAZER@EXAMPLE.COM"]
)
def test_duplicates_have_identical_response_and_do_not_update_consent(
    api_client, signup_payload, email, settings
):
    """Не менять ответ и исходное согласие при повторной заявке."""
    first_response = api_client.post(
        SIGNUPS_URL, signup_payload, format="json"
    )
    original = BetaSignup.objects.get()
    original_consented_at = original.consented_at
    original_created_at = original.created_at
    settings.PRIVACY_POLICY_VERSION = "test-v2"
    signup_payload["email"] = email

    repeated_response = api_client.post(
        SIGNUPS_URL, signup_payload, format="json"
    )

    assert first_response.status_code == repeated_response.status_code == 202
    assert (
        first_response.json() == repeated_response.json() == ACCEPTED_RESPONSE
    )
    assert BetaSignup.objects.count() == 1
    original.refresh_from_db()
    assert original.consented_at == original_consented_at
    assert original.created_at == original_created_at
    assert original.privacy_policy_version == "test-v1"


@pytest.mark.parametrize(
    "consent", [False, None, "true", "false", 1, 0, [], {}]
)
def test_consent_requires_literal_json_true(
    api_client, signup_payload, consent
):
    """Принимать согласие только в виде логического JSON true."""
    signup_payload["consent"] = consent

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 400
    assert "consent" in response.json()
    assert not BetaSignup.objects.exists()


def test_consent_is_required(api_client, signup_payload):
    """Отклонить заявку без поля согласия и не создавать запись."""
    del signup_payload["consent"]

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 400
    assert "consent" in response.json()
    assert not BetaSignup.objects.exists()


@pytest.mark.parametrize(
    "email",
    ["", "not-an-email", "@example.com", "name@", None, ["a@example.com"]],
)
def test_invalid_emails_are_rejected(api_client, signup_payload, email):
    """Отклонить некорректный email без записи персональных данных."""
    signup_payload["email"] = email

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 400
    assert "email" in response.json()
    assert not BetaSignup.objects.exists()


def test_email_is_required(api_client, signup_payload):
    """Отклонить заявку без email и не создавать запись."""
    del signup_payload["email"]

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 400
    assert "email" in response.json()
    assert not BetaSignup.objects.exists()


def test_honeypot_returns_the_same_accepted_response_without_saving(
    api_client, signup_payload
):
    """Вернуть обычный ответ на ловушку без сохранения заявки."""
    signup_payload["website"] = "https://spam.example.com"

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 202
    assert response.json() == ACCEPTED_RESPONSE
    assert not BetaSignup.objects.exists()


def test_optional_honeypot_can_be_omitted(api_client, signup_payload):
    """Принять корректную заявку без необязательного поля ловушки."""
    del signup_payload["website"]

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 202
    assert BetaSignup.objects.count() == 1


def test_client_cannot_set_status_timestamps_or_policy_version(
    api_client, signup_payload
):
    """Не позволять клиенту задавать даты, статус и политику."""
    signup_payload.update(
        {
            "status": "invited",
            "created_at": "2000-01-01T00:00:00Z",
            "consented_at": "2000-01-01T00:00:00Z",
            "privacy_policy_version": "unapproved-client-version",
            "id": 999999,
        }
    )
    before_request = timezone.now()

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 202
    signup = BetaSignup.objects.get()
    assert signup.status == "new"
    assert signup.privacy_policy_version == "test-v1"
    assert signup.created_at >= before_request
    assert signup.consented_at >= before_request
    assert signup.pk != 999999


def test_disabled_collection_does_not_save_personal_data(
    api_client, signup_payload, settings
):
    """Не собирать и не отражать email, когда приём заявок выключен."""
    settings.PUBLIC_SIGNUPS_ENABLED = False

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 503
    assert not BetaSignup.objects.exists()
    assert signup_payload["email"] not in response.content.decode()


def test_missing_policy_version_prevents_collection(
    api_client, signup_payload, settings
):
    """Запретить сохранение заявки без серверной версии политики."""
    settings.PRIVACY_POLICY_VERSION = ""

    response = api_client.post(SIGNUPS_URL, signup_payload, format="json")

    assert response.status_code == 503
    assert not BetaSignup.objects.exists()


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete", "head"])
def test_public_endpoint_never_lists_or_edits_signups(
    api_client, signup_payload, method
):
    """Запретить чтение и изменение заявок через публичный адрес API."""
    assert (
        api_client.post(SIGNUPS_URL, signup_payload, format="json").status_code
        == 202
    )

    response = getattr(api_client, method)(SIGNUPS_URL)

    assert response.status_code == 405
    assert signup_payload["email"] not in response.content.decode()
    assert BetaSignup.objects.count() == 1


def test_options_is_available_without_exposing_personal_data(api_client):
    """Описать разрешённый POST через OPTIONS без раскрытия заявок."""
    response = api_client.options(SIGNUPS_URL)

    assert response.status_code == 200
    assert "POST" in response["Allow"]
    assert "GET" not in response["Allow"]


def test_form_encoded_requests_are_rejected(api_client, signup_payload):
    """Отклонить multipart-запрос к API, принимающему только JSON."""
    response = api_client.post(SIGNUPS_URL, signup_payload, format="multipart")

    assert response.status_code == 415
    assert not BetaSignup.objects.exists()


def test_malformed_json_is_rejected(api_client):
    """Вернуть ошибку для повреждённого JSON и не создавать заявку."""
    response = api_client.generic(
        "POST", SIGNUPS_URL, data='{"email":', content_type="application/json"
    )

    assert response.status_code == 400
    assert not BetaSignup.objects.exists()


def test_database_enforces_case_insensitive_uniqueness_even_for_bulk_writes():
    """Запретить дубликаты email в базе при массовой записи."""
    now = timezone.now()
    BetaSignup.objects.create(
        email="stargazer@example.com",
        consented_at=now,
        privacy_policy_version="test-v1",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        BetaSignup.objects.bulk_create(
            [
                BetaSignup(
                    email="STARGAZER@EXAMPLE.COM",
                    consented_at=now,
                    privacy_policy_version="test-v1",
                )
            ]
        )

    assert BetaSignup.objects.count() == 1
