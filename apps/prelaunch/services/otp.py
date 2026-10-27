
import logging
import re
import secrets
from datetime import timedelta
from apps.prelaunch.providers.exceptions import OTPDeliveryUncertain
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from apps.prelaunch.models import OTPVerification, WaitlistEntry
from apps.prelaunch.providers.development import DevelopmentOTPProvider
from apps.prelaunch.providers.orange_sms import OrangeSMSProvider


logger = logging.getLogger(__name__)

OTP_EXPIRATION_MINUTES = 5
OTP_MAX_ATTEMPTS = 5


def get_otp_provider():
    provider_name = getattr(
        settings,
        "PRELAUNCH_OTP_PROVIDER",
        "disabled",
    )

    if provider_name == "development":
        return DevelopmentOTPProvider()

    if provider_name == "orange_sms":
        return OrangeSMSProvider()

    raise ImproperlyConfigured(
        f"Unsupported OTP provider: {provider_name}"
    )


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

@transaction.atomic
def create_otp(waitlist_entry):
    provider = get_otp_provider()

     # Lock this waitlist entry until the transaction finishes.
    waitlist_entry = (
        WaitlistEntry.objects.select_for_update()
        .get(pk=waitlist_entry.pk)
    )

    provider = get_otp_provider()
    if waitlist_entry.status == WaitlistEntry.Status.VERIFIED:
        raise ValueError(
            "This waitlist entry is already verified."
        )

    code = generate_otp()

    verification = OTPVerification.objects.create(
        waitlist_entry=waitlist_entry,
        code_hash=make_password(code),
        expires_at=timezone.now()
        + timedelta(minutes=OTP_EXPIRATION_MINUTES),
    )

    try:
        provider.send_code(waitlist_entry.phone, code)

    except OTPDeliveryUncertain:
        # Orange a peut-être accepté le SMS.
        # Conserver l'OTP afin qu'il reste vérifiable.
        verification.delivery_uncertain = True

        logger.warning(
            "OTP delivery uncertain for waitlist entry %s",
            waitlist_entry.id,
        )

    except Exception:
        # Échec confirmé : ne pas conserver ce nouvel OTP.
        verification.delete()

        logger.exception(
            "OTP delivery failed for waitlist entry %s",
            waitlist_entry.id,
        )
        raise

    
    # Invalider les anciens OTP uniquement lorsque
    # le fournisseur a confirmé l'acceptation de la demande.
    if not getattr(verification, "delivery_uncertain", False):
        OTPVerification.objects.filter(
            waitlist_entry=waitlist_entry,
            verified_at__isnull=True,
        ).exclude(
            id=verification.id,
        ).update(
            expires_at=timezone.now(),
        )


    return verification


    
@transaction.atomic
def verify_otp(verification_id, code: str) -> bool:
    if not isinstance(code, str) or not re.fullmatch(
        r"[0-9]{6}", code
    ):
        return False

    # Retrouver l'inscription associée au code.
    entry_id = (
        OTPVerification.objects
        .filter(id=verification_id)
        .values_list("waitlist_entry_id", flat=True)
        .get()
    )

    # Verrouiller l'inscription avant le code OTP.
    entry = (
        WaitlistEntry.objects.select_for_update()
        .get(pk=entry_id)
    )

    # Interdire toute nouvelle validation d'un numéro confirmé.
    if entry.status == WaitlistEntry.Status.VERIFIED:
        return False

    verification = (
        OTPVerification.objects.select_for_update()
        .get(
            id=verification_id,
            waitlist_entry=entry,
        )
    )

    now = timezone.now()

    if (
        verification.verified_at is not None
        or now >= verification.expires_at
        or verification.attempts >= OTP_MAX_ATTEMPTS
    ):
        return False

    verification.attempts += 1

    if not check_password(code, verification.code_hash):
        verification.save(update_fields=["attempts"])
        return False

    verification.verified_at = now
    verification.save(
        update_fields=["verified_at", "attempts"]
    )

    entry.status = WaitlistEntry.Status.VERIFIED
    entry.phone_verified_at = now
    entry.save(
        update_fields=[
            "status",
            "phone_verified_at",
            "updated_at",
        ]
    )

    # Invalider tous les autres codes de cette inscription.
    OTPVerification.objects.filter(
        waitlist_entry=entry,
        verified_at__isnull=True,
    ).exclude(
        id=verification.id,
    ).update(expires_at=now)

    return True
