from django.db import models
from django.db.models.functions import Lower


class BetaSignup(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        INVITED = "invited", "Приглашён"
        ARCHIVED = "archived", "В архиве"

    email = models.EmailField("Email", max_length=254)
    status = models.CharField("Статус", max_length=16, choices=Status, default=Status.NEW)
    created_at = models.DateTimeField("Дата заявки", auto_now_add=True)
    consented_at = models.DateTimeField("Дата согласия", editable=False)
    privacy_policy_version = models.CharField("Версия политики", max_length=100, editable=False)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Заявка в бета-тест"
        verbose_name_plural = "Заявки в бета-тест"
        constraints = [models.UniqueConstraint(Lower("email"), name="beta_signup_email_ci_unique")]

    def __str__(self):
        return self.email
