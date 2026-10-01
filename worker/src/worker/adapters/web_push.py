import asyncio
import logging
from typing import Any

from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


class SubscriptionExpiredError(Exception):
    """Raised when the push subscription has expired.

    Triggers on HTTP 410 Gone or 404 Not Found.
    """

    pass


class WebPushProvider:
    def __init__(
        self,
        private_key: str,
        claims_email: str,
        timeout: float = 10.0,
    ):
        self.private_key = private_key
        self.claims = {"sub": f"mailto:{claims_email}"}
        self.timeout = timeout

    async def send_push(self, subscription_info: dict[str, Any], payload: str) -> None:
        """Send a web push notification asynchronously using a thread pool."""
        await asyncio.to_thread(self._send, subscription_info, payload)

    def _send(self, subscription_info: dict[str, Any], payload: str) -> None:
        if not self.private_key or self.private_key.startswith("MOCK_"):
            logger.info(
                f"[MOCK PUSH] Mock VAPID key used. Logged notification:\n"
                f"  Endpoint: {subscription_info.get('endpoint')}\n"
                f"  Payload: {payload}"
            )
            return

        try:
            # webpush is a synchronous function inside pywebpush
            # timeout is forwarded to the underlying requests call so a hung
            # push endpoint cannot block the worker thread indefinitely.
            response = webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.private_key,
                vapid_claims=self.claims,
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                logger.error(
                    f"Web push server returned error: "
                    f"{response.status_code} {response.text}"
                )
                response.raise_for_status()
        except WebPushException as ex:
            response = getattr(ex, "response", None)
            if response is not None:
                if response.status_code == 410:
                    logger.warning(
                        f"Subscription expired (410 Gone) for endpoint: "
                        f"{subscription_info.get('endpoint')}"
                    )
                    raise SubscriptionExpiredError(
                        "Push subscription has expired"
                    ) from ex
                elif response.status_code == 404:
                    logger.warning(
                        f"Subscription not found (404 Not Found) for endpoint: "
                        f"{subscription_info.get('endpoint')}"
                    )
                    raise SubscriptionExpiredError(
                        "Push subscription not found"
                    ) from ex
            raise ex
