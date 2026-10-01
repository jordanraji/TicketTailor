import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

api_root = Path(__file__).resolve().parents[3]
env_path = api_root / ".env"
load_dotenv(dotenv_path=env_path)


# Placeholder dev default; the guard at the bottom of this module rejects it
# outside development/test, which is the whole point of naming it here.
DEFAULT_SECRET_KEY = "super-secret-dev-key-change-me-in-production"  # nosec B105


class Settings(BaseModel):
    # Deployment environment. Any value other than "development" / "test"
    # enables the production guards below (e.g. reject the default SECRET_KEY).
    ENVIRONMENT: str = Field(default="development")

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/tickettailor"
    )
    DATABASE_REPLICA_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/tickettailor"
    )

    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Connection-pool and timeout tuning. The pool is per-process, so the
    # effective connection count against RDS is roughly
    #   tasks * uvicorn_workers * (DB_POOL_SIZE + DB_MAX_OVERFLOW) * 2 engines.
    # Keep that under the RDS max_connections ceiling (see infra). Defaults are
    # deliberately conservative so an autoscaled fleet does not exhaust RDS.
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=5)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800)
    # Per-statement server-side timeout (asyncpg statement_timeout). Bounds a
    # slow query so it cannot pin a pooled connection indefinitely under load.
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=15000)
    # Client-side ceiling for a single asyncpg command (network round-trip).
    DB_COMMAND_TIMEOUT_SECONDS: int = Field(default=30)

    # Redis socket timeouts so a half-open connection (e.g. during an
    # ElastiCache failover) fails fast and the service falls back to the DB
    # count rather than hanging the event loop (ADR-0005).
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(default=2.0)

    SECRET_KEY: str = Field(default=DEFAULT_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AWS_REGION: str = Field(default="ap-southeast-2")
    AWS_SNS_TOPIC_ARN: str | None = Field(default=None)

    EMAIL_PROVIDER: str = Field(default="smtp")
    EMAIL_FROM_ADDRESS: str = Field(default="noreply@tickettailor.local")
    RESEND_API_KEY: str | None = Field(default=None)
    SMTP_HOST: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=1025)

    VAPID_PUBLIC_KEY: str = Field(default="MOCK_VAPID_PUBLIC_KEY_PLACEHOLDER")

    # Comma-separated list of allowed CORS origins for the SPA frontend.
    CORS_ALLOWED_ORIGINS: str = Field(default="http://localhost:3000")


settings = Settings(
    ENVIRONMENT=os.getenv("ENVIRONMENT", "development"),
    DATABASE_URL=os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/tickettailor",
    ),
    DATABASE_REPLICA_URL=os.getenv(
        "DATABASE_REPLICA_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/tickettailor",
        ),
    ),
    REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    DB_POOL_SIZE=int(os.getenv("DB_POOL_SIZE", "5")),
    DB_MAX_OVERFLOW=int(os.getenv("DB_MAX_OVERFLOW", "5")),
    DB_POOL_RECYCLE_SECONDS=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
    DB_STATEMENT_TIMEOUT_MS=int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "15000")),
    DB_COMMAND_TIMEOUT_SECONDS=int(os.getenv("DB_COMMAND_TIMEOUT_SECONDS", "30")),
    REDIS_SOCKET_TIMEOUT_SECONDS=float(
        os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "2.0")
    ),
    SECRET_KEY=os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY),
    ACCESS_TOKEN_EXPIRE_MINUTES=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
    REFRESH_TOKEN_EXPIRE_DAYS=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    AWS_REGION=os.getenv("AWS_REGION", "ap-southeast-2"),
    AWS_SNS_TOPIC_ARN=os.getenv("AWS_SNS_TOPIC_ARN"),
    EMAIL_PROVIDER=os.getenv("EMAIL_PROVIDER", "smtp"),
    EMAIL_FROM_ADDRESS=os.getenv("EMAIL_FROM_ADDRESS", "noreply@tickettailor.local"),
    RESEND_API_KEY=os.getenv("RESEND_API_KEY"),
    SMTP_HOST=os.getenv("SMTP_HOST", "localhost"),
    SMTP_PORT=int(os.getenv("SMTP_PORT", "1025")),
    VAPID_PUBLIC_KEY=os.getenv("VAPID_PUBLIC_KEY", "MOCK_VAPID_PUBLIC_KEY_PLACEHOLDER"),
    CORS_ALLOWED_ORIGINS=os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000"),
)


# Production guard: never boot a deployed environment with the known default JWT
# signing key, or anyone could forge access tokens. Only enforced outside local
# development/test so the default keeps working for those.
if (
    settings.ENVIRONMENT not in ("development", "test")
    and settings.SECRET_KEY == DEFAULT_SECRET_KEY
):
    raise RuntimeError(
        "SECRET_KEY is the built-in default but ENVIRONMENT="
        f"{settings.ENVIRONMENT!r}. Set a real SECRET_KEY before deploying."
    )
