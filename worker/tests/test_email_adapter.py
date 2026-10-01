from unittest.mock import MagicMock, patch

import pytest

from worker.adapters.email import (
    LoggingEmailProvider,
    ResendProvider,
    SmtpProvider,
    get_email_provider,
)


@pytest.mark.asyncio
async def test_smtp_provider_sends_email() -> None:
    provider = SmtpProvider(
        host="localhost", port=1025, from_address="sender@example.com"
    )

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_instance = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance

        await provider.send_email(
            to_address="recipient@example.com",
            subject="Test Subject",
            html_content="<p>Test</p>",
        )

        mock_smtp_class.assert_called_once_with("localhost", 1025, timeout=10.0)
        mock_smtp_instance.sendmail.assert_called_once()
        args = mock_smtp_instance.sendmail.call_args[0]
        assert args[0] == "sender@example.com"
        assert args[1] == "recipient@example.com"
        assert "Subject: Test Subject" in args[2]


@pytest.mark.asyncio
async def test_resend_provider_sends_email() -> None:
    provider = ResendProvider(
        api_key="resend-key-123", from_address="sender@example.com"
    )

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        await provider.send_email(
            to_address="recipient@example.com",
            subject="Test Subject",
            html_content="<p>Test</p>",
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["from"] == "sender@example.com"
        assert call_kwargs["json"]["to"] == "recipient@example.com"
        assert call_kwargs["json"]["subject"] == "Test Subject"
        assert call_kwargs["json"]["html"] == "<p>Test</p>"
        assert call_kwargs["headers"]["Authorization"] == "Bearer resend-key-123"


def test_get_email_provider_factory() -> None:
    smtp_provider = get_email_provider(
        email_provider_type="smtp",
        from_address="sender@example.com",
        resend_api_key=None,
        smtp_host="localhost",
        smtp_port=1025,
    )
    assert isinstance(smtp_provider, SmtpProvider)

    resend_provider = get_email_provider(
        email_provider_type="resend",
        from_address="sender@example.com",
        resend_api_key="some-key",
        smtp_host="localhost",
        smtp_port=1025,
    )
    assert isinstance(resend_provider, ResendProvider)

    # An absent Resend key must NOT crash the worker - it degrades to a logging
    # no-op so a misconfigured email channel cannot take down web-push delivery.
    fallback = get_email_provider(
        email_provider_type="resend",
        from_address="sender@example.com",
        resend_api_key=None,
        smtp_host="localhost",
        smtp_port=1025,
    )
    assert isinstance(fallback, LoggingEmailProvider)

    empty_key_fallback = get_email_provider(
        email_provider_type="resend",
        from_address="sender@example.com",
        resend_api_key="",
        smtp_host="localhost",
        smtp_port=1025,
    )
    assert isinstance(empty_key_fallback, LoggingEmailProvider)

    # The no-op can also be selected explicitly.
    logging_provider = get_email_provider(
        email_provider_type="logging",
        from_address="sender@example.com",
        resend_api_key=None,
        smtp_host="localhost",
        smtp_port=1025,
    )
    assert isinstance(logging_provider, LoggingEmailProvider)


@pytest.mark.asyncio
async def test_logging_email_provider_is_a_noop() -> None:
    """The logging provider 'succeeds' without any network call, so an
    email-only notification record is still acked (the load-test fan-out
    signal) when real email is disabled."""
    provider = LoggingEmailProvider(from_address="sender@example.com")
    # Must not raise and must not touch the network.
    await provider.send_email(
        to_address="recipient@example.com",
        subject="Subject",
        html_content="<p>body</p>",
    )
