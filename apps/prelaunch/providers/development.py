import hashlib

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from .base import OTPProvider


class DevelopmentOTPProvider(OTPProvider):
    def __init__(self):
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                "DevelopmentOTPProvider cannot run in production."
            )

    def send_code(self, phone: str, code: str) -> None:
        phone_hash = hashlib.sha256(
            phone.encode("utf-8")
        ).hexdigest()

        cache.set(
            f"prelaunch:dev:otp:{phone_hash}",
            code,
            timeout=300,
        )