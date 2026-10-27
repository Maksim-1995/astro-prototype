"""Публичная отправка заявки и проверка доступности PostgreSQL."""

from django.conf import settings
from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import BetaSignupSerializer
from .services import register_signup
from .throttling import BetaSignupBurstThrottle, BetaSignupDailyThrottle

ACCEPTED_MESSAGE = (
    "Заявка принята. Если вы ещё не в списке, мы добавим ваш email."
)


class BetaSignupView(APIView):
    """Принимает заявки, не раскрывая наличие email в базе."""

    permission_classes = [AllowAny]
    throttle_classes = [BetaSignupBurstThrottle, BetaSignupDailyThrottle]
    http_method_names = ["post", "options"]

    def post(self, request):
        """Проверяет согласие и сохраняет новую заявку."""
        if (
            not settings.PUBLIC_SIGNUPS_ENABLED
            or not settings.PRIVACY_POLICY_VERSION
        ):
            return Response(
                {"detail": "Приём заявок пока не открыт."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = BetaSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data.get("website"):
            register_signup(email=serializer.validated_data["email"])
        # Единый ответ не раскрывает, зарегистрирован ли этот email.
        return Response(
            {"detail": ACCEPTED_MESSAGE}, status=status.HTTP_202_ACCEPTED
        )


class HealthView(APIView):
    """Проверяет доступность БД без раскрытия деталей."""

    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        """Выполняет SELECT 1 и возвращает состояние соединения."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return Response(
                {"status": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok"})
