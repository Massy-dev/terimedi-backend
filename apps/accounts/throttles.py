from rest_framework.throttling import AnonRateThrottle


class OTPRequestThrottle(AnonRateThrottle):
    scope = "otp_request"