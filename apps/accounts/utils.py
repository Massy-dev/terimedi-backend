import phonenumbers
from django.core.exceptions import ValidationError


def normalize_phone_number(phone_number: str) -> str:
    if not phone_number:
        raise ValidationError("Phone number is required.")

    try:
        parsed_number = phonenumbers.parse(phone_number, "CI")
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("Invalid phone number.") from exc

    if not phonenumbers.is_valid_number(parsed_number):
        raise ValidationError("Invalid phone number.")

    return phonenumbers.format_number(
        parsed_number,
        phonenumbers.PhoneNumberFormat.E164,
    )