from unittest.mock import MagicMock, patch

import pytest
from py_vapid import Vapid
from pywebpush import WebPushException

from worker.adapters.web_push import SubscriptionExpiredError, WebPushProvider


@pytest.fixture(scope="session")
def valid_vapid_private_key() -> str:
    """Generate a valid VAPID private key in PEM format for test parsing."""
    vapid = Vapid()
    vapid.generate_keys()
    return vapid.private_pem().decode("utf-8")


@pytest.mark.asyncio
async def test_web_push_mock_key_logs_and_returns() -> None:
    provider = WebPushProvider(
        private_key="MOCK_PRIVATE_KEY", claims_email="admin@example.com"
    )

    with patch("worker.adapters.web_push.webpush") as mock_webpush:
        await provider.send_push(
            subscription_info={"endpoint": "http://localhost/push"},
            payload="test payload",
        )
        mock_webpush.assert_not_called()


@pytest.mark.asyncio
async def test_web_push_success(valid_vapid_private_key: str) -> None:
    provider = WebPushProvider(
        private_key=valid_vapid_private_key, claims_email="admin@example.com"
    )

    sub_info = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/some-token",
        "keys": {"p256dh": "some-dh", "auth": "some-auth"},
    }

    with patch("worker.adapters.web_push.webpush") as mock_webpush:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_webpush.return_value = mock_response

        await provider.send_push(sub_info, "hello world")

        mock_webpush.assert_called_once_with(
            subscription_info=sub_info,
            data="hello world",
            vapid_private_key=valid_vapid_private_key,
            vapid_claims={"sub": "mailto:admin@example.com"},
            timeout=10.0,
        )


@pytest.mark.asyncio
async def test_web_push_subscription_expired_410(
    valid_vapid_private_key: str,
) -> None:
    provider = WebPushProvider(
        private_key=valid_vapid_private_key, claims_email="admin@example.com"
    )

    sub_info = {"endpoint": "https://push.com/send"}

    with patch("worker.adapters.web_push.webpush") as mock_webpush:
        mock_response = MagicMock()
        mock_response.status_code = 410
        ex = WebPushException("Subscription gone", response=mock_response)
        mock_webpush.side_effect = ex

        with pytest.raises(
            SubscriptionExpiredError, match="Push subscription has expired"
        ):
            await provider.send_push(sub_info, "hello")


@pytest.mark.asyncio
async def test_web_push_subscription_not_found_404(
    valid_vapid_private_key: str,
) -> None:
    provider = WebPushProvider(
        private_key=valid_vapid_private_key, claims_email="admin@example.com"
    )

    sub_info = {"endpoint": "https://push.com/send"}

    with patch("worker.adapters.web_push.webpush") as mock_webpush:
        mock_response = MagicMock()
        mock_response.status_code = 404
        ex = WebPushException("Not found", response=mock_response)
        mock_webpush.side_effect = ex

        with pytest.raises(
            SubscriptionExpiredError, match="Push subscription not found"
        ):
            await provider.send_push(sub_info, "hello")


@pytest.mark.asyncio
async def test_web_push_other_error(valid_vapid_private_key: str) -> None:
    provider = WebPushProvider(
        private_key=valid_vapid_private_key, claims_email="admin@example.com"
    )

    sub_info = {"endpoint": "https://push.com/send"}

    with patch("worker.adapters.web_push.webpush") as mock_webpush:
        mock_response = MagicMock()
        mock_response.status_code = 500
        ex = WebPushException("Internal Server Error", response=mock_response)
        mock_webpush.side_effect = ex

        with pytest.raises(WebPushException, match="Internal Server Error"):
            await provider.send_push(sub_info, "hello")
