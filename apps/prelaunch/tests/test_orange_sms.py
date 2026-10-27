from requests.exceptions import HTTPError
from unittest.mock import Mock, patch
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from apps.prelaunch.providers.orange_sms import OrangeSMSProvider


@override_settings(
    ORANGE_CLIENT_ID="test-client-id",
    ORANGE_CLIENT_SECRET="test-client-secret",
    ORANGE_SMS_SENDER_NAME="TERIMEDI",
    ORANGE_SMS_SENDER_ADDRESS="+2250000",
)
class OrangeSMSProviderTests(SimpleTestCase):

    def setUp(self):
        self.provider = OrangeSMSProvider()
        cache.delete(self.provider.token_cache_key)

    @patch("apps.prelaunch.providers.orange_sms.requests.post")
    def test_get_access_token(self, mock_post):
        response = Mock()
        response.json.return_value = {
            "access_token": "fake-orange-token",
            "expires_in": 3600,
        }
        mock_post.return_value = response

        token = self.provider._get_access_token()

        self.assertEqual(token, "fake-orange-token")
        self.assertEqual(mock_post.call_count, 1)

        # Second request should use Redis cache.
        self.provider._get_access_token()
        self.assertEqual(mock_post.call_count, 1)

    @patch("apps.prelaunch.providers.orange_sms.requests.post")
    def test_send_code(self, mock_post):
        cache.set(
            self.provider.token_cache_key,
            "fake-orange-token",
            timeout=300,
        )

        response = Mock()
        response.status_code = 201
        mock_post.return_value = response

        self.provider.send_code(
            "+2250700000001",
            "123456",
        )

        args, kwargs = mock_post.call_args

        self.assertEqual(args[0], self.provider.sms_url)
        self.assertEqual(
            kwargs["json"]["outboundSMSMessageRequest"]["address"],
            "tel:+2250700000001",
        )
        self.assertEqual(
            kwargs["json"]["outboundSMSMessageRequest"]["senderName"],
            "TERIMEDI",
        )
        self.assertEqual(mock_post.call_count, 1)
      
    
    @patch("apps.prelaunch.providers.orange_sms.requests.post")
    def test_oauth_http_error(self, mock_post):
        response = Mock()
        response.raise_for_status.side_effect = HTTPError(
            "Orange OAuth authentication failed"
        )
        mock_post.return_value = response

        with self.assertRaises(HTTPError):
            self.provider._get_access_token()

        self.assertEqual(mock_post.call_count, 1)

    @patch("apps.prelaunch.providers.orange_sms.requests.post")
    def test_sms_http_error(self, mock_post):
        cache.set(
            self.provider.token_cache_key,
            "fake-orange-token",
            timeout=300,
        )

        response = Mock()
        response.raise_for_status.side_effect = HTTPError(
            "Orange SMS request failed"
        )
        mock_post.return_value = response

        with self.assertRaises(HTTPError):
            self.provider.send_code(
                "+2250700000001",
                "123456",
            )

        self.assertEqual(mock_post.call_count, 1)

    
    @patch(
        "apps.prelaunch.providers.orange_sms.requests.post"
    )
    def test_refresh_token_after_401(self, mock_post):
        from unittest.mock import Mock

        from apps.prelaunch.providers.orange_sms import OrangeSMSProvider

        provider = OrangeSMSProvider()

        # Start with a cached token that Orange has revoked.
        from django.core.cache import cache

        cache.set(
            provider.token_cache_key,
            "expired-token",
            timeout=300,
        )

        unauthorized_response = Mock()
        unauthorized_response.status_code = 401

        token_response = Mock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }

        success_response = Mock()
        success_response.status_code = 201

        mock_post.side_effect = [
            unauthorized_response,
            token_response,
            success_response,
        ]

        provider.send_code(
            "+2250700000001",
            "123456",
        )

        self.assertEqual(mock_post.call_count, 3)

        # First SMS request uses the expired token.
        self.assertEqual(
            mock_post.call_args_list[0].kwargs["headers"][
                "Authorization"
            ],
            "Bearer expired-token",
        )

        # The second SMS request uses the refreshed token.
        self.assertEqual(
            mock_post.call_args_list[2].kwargs["headers"][
                "Authorization"
            ],
            "Bearer new-token",
        )

        self.assertEqual(
            cache.get(provider.token_cache_key),
            "new-token",
        )


    
    @patch(
        "apps.prelaunch.providers.orange_sms.requests.post"
    )
    def test_no_retry_after_sms_network_timeout(self, mock_post):
        import requests

        from django.core.cache import cache
        from apps.prelaunch.providers.orange_sms import OrangeSMSProvider

        provider = OrangeSMSProvider()

        # Avoid an OAuth request by providing a cached token.
        cache.set(
            provider.token_cache_key,
            "valid-test-token",
            timeout=300,
        )

        # Simulate a network timeout during SMS submission.
        mock_post.side_effect = requests.exceptions.Timeout(
            "Orange SMS request timed out"
        )

        from apps.prelaunch.providers.exceptions import (
            OTPDeliveryUncertain,
        )

        with self.assertRaises(OTPDeliveryUncertain):
            provider.send_code(
                "+2250700000001",
                "123456",
            )

        # Only one HTTP request must have been attempted.
        self.assertEqual(mock_post.call_count, 1)

