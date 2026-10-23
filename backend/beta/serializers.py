from rest_framework import serializers


class NormalizedEmailField(serializers.EmailField):
    def to_internal_value(self, data):
        # Lowercasing some Unicode characters increases their length. Normalize
        # before EmailField validators so the value stored in PostgreSQL is checked.
        return super().to_internal_value(data).lower()


class ConsentField(serializers.BooleanField):
    default_error_messages = {"invalid": "Подтвердите согласие на обработку персональных данных."}

    def to_internal_value(self, data):
        if data is not True:
            self.fail("invalid")
        return True


class BetaSignupSerializer(serializers.Serializer):
    email = NormalizedEmailField(max_length=254)
    consent = ConsentField()
    website = serializers.CharField(
        required=False, allow_blank=True, max_length=200, write_only=True
    )
