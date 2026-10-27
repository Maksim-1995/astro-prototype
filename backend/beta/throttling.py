"""Ограничения частоты отправки заявок по адресу клиента."""

from rest_framework.throttling import AnonRateThrottle


class BetaSignupBurstThrottle(AnonRateThrottle):
    """Ограничивает кратковременные серии запросов с одного IP."""

    scope = "beta_signup_burst"


class BetaSignupDailyThrottle(AnonRateThrottle):
    """Ограничивает число запросов с одного IP за скользящие сутки."""

    scope = "beta_signup_daily"
