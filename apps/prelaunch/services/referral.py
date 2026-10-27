import secrets

from django.db import IntegrityError, transaction

from apps.prelaunch.models import WaitlistEntry


def generate_referral_code():
    return "TM-" + secrets.token_hex(4).upper()


def assign_referral_code(entry):
    if entry.status != WaitlistEntry.Status.VERIFIED:
        raise ValueError(
            "Only verified entries can receive a referral code."
        )

    if entry.referral_code:
        return entry.referral_code

    for _ in range(5):
        code = generate_referral_code()

        try:
            with transaction.atomic():
                updated = WaitlistEntry.objects.filter(
                    pk=entry.pk,
                    referral_code__isnull=True,
                ).update(referral_code=code)

                if updated:
                    entry.referral_code = code
                    return code

                entry.refresh_from_db(
                    fields=["referral_code"],
                )
                return entry.referral_code

        except IntegrityError:
            continue

    raise RuntimeError(
        "Unable to generate a unique referral code."
    )


def get_referral_count(entry):
    if entry.status != WaitlistEntry.Status.VERIFIED:
        return 0

    return WaitlistEntry.objects.filter(
        referred_by=entry,
        status=WaitlistEntry.Status.VERIFIED,
    ).count()