import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


class EmailProvider(Protocol):
    async def send_email(
        self, to_address: str, subject: str, html_content: str
    ) -> None:
        """Send an email asynchronously."""
        ...


DEFAULT_TIMEOUT_SECONDS = 10.0


class SmtpProvider:
    def __init__(
        self,
        host: str,
        port: int,
        from_address: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.host = host
        self.port = port
        self.from_address = from_address
        self.timeout = timeout

    async def send_email(
        self, to_address: str, subject: str, html_content: str
    ) -> None:
        """Send an email using SMTP client via thread pool to avoid blocking."""
        await asyncio.to_thread(self._send, to_address, subject, html_content)

    def _send(self, to_address: str, subject: str, html_content: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = to_address

        part = MIMEText(html_content, "html")
        msg.attach(part)

        logger.info(
            f"Sending SMTP email from {self.from_address} to {to_address} "
            f"(via {self.host}:{self.port})"
        )
        # timeout bounds the connect/SMTP socket so a hung mail server cannot
        # block the worker thread indefinitely (default would be the OS default,
        # which can be minutes).
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
            server.sendmail(self.from_address, to_address, msg.as_string())


class ResendProvider:
    def __init__(
        self,
        api_key: str,
        from_address: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.api_key = api_key
        self.from_address = from_address
        self.url = "https://api.resend.com/emails"
        self.timeout = timeout

    async def send_email(
        self, to_address: str, subject: str, html_content: str
    ) -> None:
        """Send an email using Resend API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.from_address,
            "to": to_address,
            "subject": subject,
            "html": html_content,
        }
        logger.info(
            f"Sending Resend API email from {self.from_address} to {to_address}"
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(
                    f"Failed to send email via Resend: "
                    f"{response.status_code} {response.text}"
                )
                response.raise_for_status()


class LoggingEmailProvider:
    """No-op email provider: logs instead of sending.

    Used when real email is intentionally disabled - e.g. the Learner Lab
    deployment has no SMTP server and no Resend key ("Empty disables real
    sends", terraform.tfvars). Delivery "succeeds" (logs and returns) so the
    notification record is acked and the worker is NOT crash-coupled to email
    configuration. Web push remains the real FR7 channel; email is best-effort.
    """

    def __init__(self, from_address: str):
        self.from_address = from_address

    async def send_email(
        self, to_address: str, subject: str, html_content: str
    ) -> None:
        logger.info(
            "[MOCK EMAIL] real sends disabled - from=%s to=%s subject=%s",
            self.from_address,
            to_address,
            subject,
        )


def get_email_provider(
    email_provider_type: str,
    from_address: str,
    resend_api_key: str | None,
    smtp_host: str,
    smtp_port: int,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> EmailProvider:
    """Factory to get the configured email provider.

    A misconfigured email channel must never crash the worker (which would take
    down web-push delivery too), so an absent Resend key degrades to a logging
    no-op rather than raising. ``logging``/``none`` select the no-op explicitly.
    """
    provider = email_provider_type.lower()
    if provider in ("logging", "none", "mock"):
        return LoggingEmailProvider(from_address=from_address)
    if provider == "resend":
        if not resend_api_key:
            # Empty key is the documented "disable real sends" config. Fall back
            # to a logging no-op instead of raising at import (which would crash
            # the Lambda cold start before any message is processed).
            logger.warning(
                "EMAIL_PROVIDER=resend but RESEND_API_KEY is empty; "
                "falling back to logging provider (no real email sent)."
            )
            return LoggingEmailProvider(from_address=from_address)
        return ResendProvider(
            api_key=resend_api_key, from_address=from_address, timeout=timeout
        )
    return SmtpProvider(
        host=smtp_host,
        port=smtp_port,
        from_address=from_address,
        timeout=timeout,
    )
