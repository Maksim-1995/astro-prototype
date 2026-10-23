from rest_framework.throttling import AnonRateThrottle


class BetaSignupBurstThrottle(AnonRateThrottle):
    scope = "beta_signup_burst"


class BetaSignupDailyThrottle(AnonRateThrottle):
    scope = "beta_signup_daily"
