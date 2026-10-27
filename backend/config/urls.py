"""Основные маршруты административной панели и API версии v1."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("beta.urls")),
]
