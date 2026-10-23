import pytest
from django.contrib.auth.models import Permission
from django.db import OperationalError, connection
from django.test import Client

from beta.models import BetaSignup
from beta.services import register_signup

pytestmark = pytest.mark.django_db


def test_health_checks_database_without_authentication(api_client):
    response = api_client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_disclose_database_error_details(api_client, monkeypatch):
    def database_unavailable(*args, **kwargs):
        raise OperationalError("database password=do-not-disclose host=private-db")

    monkeypatch.setattr(connection, "cursor", database_unavailable)

    response = api_client.get("/api/v1/health/")

    assert response.status_code == 503
    assert "do-not-disclose" not in response.content.decode()
    assert "private-db" not in response.content.decode()
    assert "OperationalError" not in response.content.decode()


def test_anonymous_cannot_access_admin(client):
    response = client.get("/admin/beta/betasignup/")

    assert response.status_code == 302
    assert response.url.startswith("/admin/login/")


def test_non_staff_cannot_access_admin(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="ordinary-user", password="test-password"
    )
    client.force_login(user)

    response = client.get("/admin/beta/betasignup/")

    assert response.status_code == 302
    assert response.url.startswith("/admin/login/")


def test_authorized_admin_can_view_signup_list(client, django_user_model):
    admin = django_user_model.objects.create_superuser(
        username="signup-admin", password="test-password", email="admin@example.com"
    )
    client.force_login(admin)

    response = client.get("/admin/beta/betasignup/")

    assert response.status_code == 200


def test_staff_without_model_permission_cannot_view_signups(client, django_user_model):
    staff = django_user_model.objects.create_user(
        username="unprivileged-staff", password="test-password", is_staff=True
    )
    client.force_login(staff)

    response = client.get("/admin/beta/betasignup/")

    assert response.status_code == 403


def test_staff_with_view_permission_can_view_signups(client, django_user_model):
    staff = django_user_model.objects.create_user(
        username="signup-reviewer", password="test-password", is_staff=True
    )
    staff.user_permissions.add(
        Permission.objects.get(codename="view_betasignup", content_type__app_label="beta")
    )
    client.force_login(staff)

    response = client.get("/admin/beta/betasignup/")

    assert response.status_code == 200


def test_admin_can_change_status_but_cannot_rewrite_original_signup(
    client, django_user_model
):
    admin = django_user_model.objects.create_superuser(
        username="signup-editor", password="test-password", email="admin@example.com"
    )
    client.force_login(admin)
    register_signup(email="stargazer@example.com")
    signup = BetaSignup.objects.get()
    original_created_at = signup.created_at
    original_consented_at = signup.consented_at

    response = client.post(
        f"/admin/beta/betasignup/{signup.pk}/change/",
        {
            "status": "invited",
            "email": "replacement@example.com",
            "created_at_0": "2000-01-01",
            "created_at_1": "00:00:00",
            "consented_at_0": "2000-01-01",
            "consented_at_1": "00:00:00",
            "privacy_policy_version": "replacement-policy",
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    signup.refresh_from_db()
    assert signup.status == BetaSignup.Status.INVITED
    assert signup.email == "stargazer@example.com"
    assert signup.created_at == original_created_at
    assert signup.consented_at == original_consented_at
    assert signup.privacy_policy_version == "test-v1"


def test_admin_change_requires_csrf_even_for_authenticated_superuser(django_user_model):
    admin = django_user_model.objects.create_superuser(
        username="csrf-admin", password="test-password", email="admin@example.com"
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin)
    register_signup(email="stargazer@example.com")
    signup = BetaSignup.objects.get()

    response = client.post(
        f"/admin/beta/betasignup/{signup.pk}/change/", {"status": "invited", "_save": "Save"}
    )

    assert response.status_code == 403
    signup.refresh_from_db()
    assert signup.status == BetaSignup.Status.NEW
