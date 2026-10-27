from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import PhoneVerification, User


class RegistrationService:
    @staticmethod
    @transaction.atomic
    def complete_registration(
        *,
        verification_id,
        password: str,
        first_name: str = "",
        last_name: str = "",
    ) -> User:
        try:
            verification = (
                PhoneVerification.objects
                .select_for_update()
                .get(id=verification_id)
            )
        except PhoneVerification.DoesNotExist as exc:
            raise ValidationError(
                "Verification not found."
            ) from exc

        if verification.purpose != PhoneVerification.Purpose.REGISTRATION:
            raise ValidationError(
                "Invalid verification purpose."
            )

        if verification.verified_at is None:
            raise ValidationError(
                "Phone number has not been verified."
            )

        if verification.consumed_at is not None:
            raise ValidationError(
                "Verification has already been consumed."
            )

        if User.objects.filter(
            phone_number=verification.phone_number
        ).exists():
            raise ValidationError(
                "An account already exists for this phone number."
            )

        try:
            user = User.objects.create_user(
                phone_number=verification.phone_number,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.PATIENT,
                is_phone_verified=True,
            )
        except IntegrityError as exc:
            raise ValidationError(
                "An account already exists for this phone number."
            ) from exc

        verification.consumed_at = timezone.now()
        verification.save(
            update_fields=["consumed_at"]
        )

        return user