import os

from worker.config import Settings


def test_default_config() -> None:
    settings = Settings()
    assert settings.EMAIL_PROVIDER == "smtp"
    assert settings.SMTP_HOST == "localhost"
    assert settings.SMTP_PORT == 1025


def test_env_override() -> None:
    os.environ["EMAIL_PROVIDER"] = "resend"
    os.environ["RESEND_API_KEY"] = "test-key"
    try:
        settings = Settings(
            EMAIL_PROVIDER=os.getenv("EMAIL_PROVIDER", "smtp"),
            RESEND_API_KEY=os.getenv("RESEND_API_KEY"),
        )
        assert settings.EMAIL_PROVIDER == "resend"
        assert settings.RESEND_API_KEY == "test-key"
    finally:
        del os.environ["EMAIL_PROVIDER"]
        del os.environ["RESEND_API_KEY"]
