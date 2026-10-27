"""Регистрация приложения бета-теста в Django."""

from django.apps import AppConfig


class BetaConfig(AppConfig):
    """Задаёт имя приложения и подпись в админке."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "beta"
    verbose_name = "Бета-тест"
