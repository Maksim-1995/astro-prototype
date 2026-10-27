"""Просмотр заявок и управление их статусами сотрудниками."""

from django.contrib import admin

from .models import BetaSignup


@admin.register(BetaSignup)
class BetaSignupAdmin(admin.ModelAdmin):
    """Позволяет искать заявки и менять статус без правки согласия."""

    list_display = (
        "email",
        "status",
        "created_at",
        "consented_at",
        "privacy_policy_version",
    )
    list_filter = ("status", "created_at", "privacy_policy_version")
    search_fields = ("email",)
    readonly_fields = (
        "email",
        "created_at",
        "consented_at",
        "privacy_policy_version",
    )
    fields = (
        "email",
        "status",
        "created_at",
        "consented_at",
        "privacy_policy_version",
    )
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request):
        """Запрещает ручное создание заявок без согласия."""
        return False
