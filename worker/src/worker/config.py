import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def find_env_file() -> Path | None:
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "worker" / ".env").exists():
            return current / "worker" / ".env"
        if (current / ".env").exists():
            return current / ".env"
        if (current / "api" / ".env").exists():
            return current / "api" / ".env"
        current = current.parent
    return None


env_path = find_env_file()
if env_path:
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Settings(BaseModel):
    EMAIL_PROVIDER: str = Field(default="smtp")
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@tickettailor.local")
    RESEND_API_KEY: str | None = Field(default=None)
    SMTP_HOST: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=1025)

    # Web Push config (ADR-0011)
    VAPID_PUBLIC_KEY: str = Field(default="MOCK_VAPID_PUBLIC_KEY_PLACEHOLDER")
    VAPID_PRIVATE_KEY: str = Field(default="MOCK_VAPID_PRIVATE_KEY_PLACEHOLDER")
    VAPID_CLAIMS_EMAIL: str = Field(default="noreply@tickettailor.local")

    # AWS configuration (ADR-0006)
    AWS_REGION: str = Field(default="ap-southeast-2")

    # Per-delivery network timeout (seconds) for email/web-push providers. Kept
    # well under the Lambda timeout so a slow provider fails fast and the
    # message is retried via batchItemFailures instead of stalling the batch
    # until SQS redelivers it on visibility-timeout expiry.
    DELIVERY_TIMEOUT_SECONDS: float = Field(default=10.0)


settings = Settings(
    EMAIL_PROVIDER=os.getenv("EMAIL_PROVIDER", "smtp"),
    EMAIL_FROM_ADDRESS=os.getenv("EMAIL_FROM_ADDRESS", "noreply@tickettailor.local"),
    RESEND_API_KEY=os.getenv("RESEND_API_KEY"),
    SMTP_HOST=os.getenv("SMTP_HOST", "localhost"),
    SMTP_PORT=int(os.getenv("SMTP_PORT", "1025")),
    VAPID_PUBLIC_KEY=os.getenv("VAPID_PUBLIC_KEY", "MOCK_VAPID_PUBLIC_KEY_PLACEHOLDER"),
    VAPID_PRIVATE_KEY=os.getenv(
        "VAPID_PRIVATE_KEY", "MOCK_VAPID_PRIVATE_KEY_PLACEHOLDER"
    ),
    VAPID_CLAIMS_EMAIL=os.getenv("VAPID_CLAIMS_EMAIL", "noreply@tickettailor.local"),
    AWS_REGION=os.getenv("AWS_REGION", "ap-southeast-2"),
    DELIVERY_TIMEOUT_SECONDS=float(os.getenv("DELIVERY_TIMEOUT_SECONDS", "10.0")),
)
