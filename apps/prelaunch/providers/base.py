from abc import ABC, abstractmethod


class OTPProvider(ABC):
    @abstractmethod
    def send_code(self, phone: str, code: str) -> None:
        """Send an OTP code to a phone number."""