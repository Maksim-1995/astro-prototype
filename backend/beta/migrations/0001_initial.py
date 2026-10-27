"""Создаёт таблицу заявок с уникальностью email без учёта регистра."""

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    """Описывает первоначальную схему хранения заявок и согласий."""

    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="BetaSignup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "email",
                    models.EmailField(max_length=254, verbose_name="Email"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Новая"),
                            ("invited", "Приглашён"),
                            ("archived", "В архиве"),
                        ],
                        default="new",
                        max_length=16,
                        verbose_name="Статус",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата заявки"
                    ),
                ),
                (
                    "consented_at",
                    models.DateTimeField(
                        editable=False, verbose_name="Дата согласия"
                    ),
                ),
                (
                    "privacy_policy_version",
                    models.CharField(
                        editable=False,
                        max_length=100,
                        verbose_name="Версия политики",
                    ),
                ),
            ],
            options={
                "verbose_name": "Заявка в бета-тест",
                "verbose_name_plural": "Заявки в бета-тест",
                "ordering": ["-created_at", "-pk"],
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("email"),
                        name="beta_signup_email_ci_unique",
                    )
                ],
            },
        ),
    ]
