from urllib.parse import quote
import base64
import logging
import hashlib
from .exceptions import OTPDeliveryUncertain
import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from .base import OTPProvider

logger = logging.getLogger(__name__)


class OrangeSMSProvider(OTPProvider):
    TOKEN_URL = "https://api.orange.com/oauth/v3/token"
    

    @property
    def sms_url(self):
        sender = f"tel:{self.sender_address}"
        encoded_sender = quote(sender, safe="")
        return (
            "https://api.orange.com/smsmessaging/v1/"
            f"outbound/{encoded_sender}/requests"
        )

    def __init__(self):
        self.client_id = getattr(settings, "ORANGE_CLIENT_ID", "")
        self.client_secret = getattr(settings, "ORANGE_CLIENT_SECRET", "")
        self.sender_name = getattr(
            settings, "ORANGE_SMS_SENDER_NAME", "TERIMEDI"
        )
        self.sender_address = getattr(
            settings, "ORANGE_SMS_SENDER_ADDRESS", ""
        )

        if not all(
            [self.client_id, self.client_secret, self.sender_address]
        ):
            raise ImproperlyConfigured(
                "Orange SMS credentials or sender address are missing."
            )
        
        credentials_hash = hashlib.sha256(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).hexdigest()

        self.token_cache_key = (
            f"prelaunch:orange:access_token:{credentials_hash}"
        )


    def _get_access_token(self):
        token = cache.get(self.token_cache_key)
        if token:
            return token

        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        response = requests.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Accept": "application/json",
            },
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        response.raise_for_status()

        payload = response.json()
        token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))

        cache.set(
            self.token_cache_key,
            token,
            timeout=max(1, expires_in - 60),
        )
        return token

    
    def _invalidate_access_token(self):
        """
        Remove a cached OAuth token when Orange rejects it.
        """
        cache.delete(self.token_cache_key)


    
    def send_code(self, phone: str, code: str) -> None:
        def send_request(token):
            return requests.post(
                self.sms_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "outboundSMSMessageRequest": {
                        "address": f"tel:{phone}",
                        "senderAddress": f"tel:{self.sender_address}",
                        "senderName": self.sender_name,
                        "outboundSMSTextMessage": {
                            "message": (
                                f"Votre code de verification TeriMedi "
                                f"est {code}. Valable 5 minutes."
                            )
                        },
                    }
                },
                timeout=15,
            )

        
        token = self._get_access_token()

        try:
            response = send_request(token)

            if response.status_code == 401:
                logger.warning(
                    "Orange SMS rejected OAuth token. Refreshing token."
                )

                self._invalidate_access_token()
                token = self._get_access_token()
                response = send_request(token)

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as exc:
            raise OTPDeliveryUncertain(
                "Orange SMS delivery status is uncertain."
            ) from exc

        response.raise_for_status()
        logger.info("Orange SMS API accepted an OTP request.")

