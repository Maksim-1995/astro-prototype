"""Проверки конфигурации до запуска приложения и обращения к базе."""

import runpy
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.py"


@pytest.mark.parametrize("version", ["", "v1", "я" * 100, "  v1  "])
def test_policy_version_accepts_valid_length(monkeypatch, version):
    """Разрешить пустую версию и максимум 100 символов без пробелов."""
    monkeypatch.setenv("DJANGO_SECRET_KEY", "settings-test-secret")
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("PRIVACY_POLICY_VERSION", version)

    config = runpy.run_path(str(SETTINGS_PATH))

    assert config["PRIVACY_POLICY_VERSION"] == version.strip()


def test_policy_version_rejects_too_long_value(monkeypatch):
    """Отклонить длинную версию до сохранения заявки в PostgreSQL."""
    monkeypatch.setenv("DJANGO_SECRET_KEY", "settings-test-secret")
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("PRIVACY_POLICY_VERSION", "я" * 101)

    with pytest.raises(ImproperlyConfigured, match="PRIVACY_POLICY_VERSION"):
        runpy.run_path(str(SETTINGS_PATH))
