from django.urls import path

from .views import BetaSignupView, HealthView

urlpatterns = [
    path("beta-signups/", BetaSignupView.as_view(), name="beta-signups"),
    path("health/", HealthView.as_view(), name="health"),
]
