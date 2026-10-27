import secrets
from datetime import timedelta
from django.db import transaction
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import PhoneVerification
from apps.accounts.utils import normalize_phone_number


class OTPService:
    @staticmethod
    def generate_code() -> str:
        length = settings.OTP_CODE_LENGTH
        upper_bound = 10 ** length

        return f"{secrets.randbelow(upper_bound):0{length}d}"

    @classmethod
    @transaction.atomic
    def create_verification(
            cls,
            phone_number: str,
            purpose: str,
    ) -> tuple[PhoneVerification, str]:
        phone_number = normalize_phone_number(phone_number)
        now = timezone.now()

        latest_verification = (
            PhoneVerification.objects
            .filter(
                phone_number=phone_number,
                purpose=purpose,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if latest_verification is not None:
            cooldown_ends_at = (
                    latest_verification.created_at
                    + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
            )

            if now < cooldown_ends_at:
                raise ValidationError(
                    "Please wait before requesting another verification code."
                )

        PhoneVerification.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            consumed_at__isnull=True,
        ).update(consumed_at=now)

        code = cls.generate_code()

        verification = PhoneVerification.objects.create(
            phone_number=phone_number,
            code_hash=make_password(code),
            purpose=purpose,
            expires_at=now
                       + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        )

        return verification, code

    @staticmethod
    def verify(
        verification: PhoneVerification,
        code: str,
    ) -> PhoneVerification:
        if verification.consumed_at is not None:
            raise ValidationError("Verification has already been consumed.")

        if verification.verified_at is not None:
            raise ValidationError("Verification has already been verified.")

        if timezone.now() >= verification.expires_at:
            raise ValidationError("Verification code has expired.")

        if verification.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise ValidationError("Maximum verification attempts exceeded.")

        verification.attempts += 1

        if not check_password(code, verification.code_hash):
            verification.save(update_fields=["attempts"])
            raise ValidationError("Invalid verification code.")

        verification.verified_at = timezone.now()
        verification.save(
            update_fields=[
                "attempts",
                "verified_at",
            ]
        )

        return verification