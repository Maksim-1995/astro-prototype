"""Проверка и нормализация данных публичной заявки."""

from rest_framework import serializers


class NormalizedEmailField(serializers.EmailField):
    """Нормализует email до проверки формата и максимальной длины."""

    def to_internal_value(self, data):
        """Возвращает строку email в нижнем регистре."""
        # Некоторые символы Unicode после lower() становятся длиннее.
        # Валидаторы должны проверять уже нормализованное значение.
        return super().to_internal_value(data).lower()


class ConsentField(serializers.BooleanField):
    """Принимает согласие только как логическое true."""

    default_error_messages = {
        "invalid": "Подтвердите согласие на обработку персональных данных."
    }

    def to_internal_value(self, data):
        """Отклоняет строки, числа и любые значения, кроме JSON true."""
        if data is not True:
            self.fail("invalid")
        return True


class BetaSignupSerializer(serializers.Serializer):
    """Проверяет email, согласие и ловушку для спам-ботов."""

    email = NormalizedEmailField(max_length=254)
    consent = ConsentField()
    website = serializers.CharField(
        required=False, allow_blank=True, max_length=200, write_only=True
    )
