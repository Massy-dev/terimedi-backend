import logging


logger = logging.getLogger(__name__)


class ConsoleSMSBackend:
    def send_otp(self, phone_number: str, code: str) -> None:
        logger.info(
            "OTP for %s: %s",
            phone_number,
            code,
        )