import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.auth.repositories import RefreshTokenRepository
from tickettailor.shared.config import settings
from tickettailor.shared.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
)
from tickettailor.shared.security import (
    create_access_token,
    generate_refresh_token,
    hash_token,
    verify_password,
)
from tickettailor.users.models import User
from tickettailor.users.repositories import UserRepository
from tickettailor.users.service import UserService


def _utc_now() -> datetime:
    """Timezone-aware UTC now.

    The ``refresh_tokens`` migration declares ``expires_at``/``revoked_at`` as
    ``TIMESTAMP WITH TIME ZONE``, and asyncpg returns timezone-aware datetimes
    from such columns. Keeping the values we write and compare aware avoids
    naive-vs-aware ``TypeError`` on read-back.
    """
    return datetime.now(UTC)


class AuthService:
    """Owns credential verification and token lifecycle (ADR-0009, ADR-0014).

    Registration delegates to the ``users`` module, which owns the profile;
    ``auth`` sits above ``users`` in the layer contract so this import is
    permitted.
    """

    def __init__(self) -> None:
        self.user_service = UserService()
        self.user_repo = UserRepository()
        self.refresh_repo = RefreshTokenRepository()

    async def register(
        self, db: AsyncSession, email: str, password: str, display_name: str
    ) -> User:
        return await self.user_service.register_user(db, email, password, display_name)

    async def authenticate(self, db: AsyncSession, email: str, password: str) -> User:
        user = await self.user_repo.get_by_email(db, email)
        # Verify even when the user is missing? We can't here, but we return a
        # uniform error so the response doesn't reveal whether the email exists.
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user

    async def issue_tokens(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> tuple[str, str]:
        access_token = create_access_token(user_id)
        refresh_token = generate_refresh_token()
        expires_at = _utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.refresh_repo.create(
            db, user_id, hash_token(refresh_token), expires_at
        )
        return access_token, refresh_token

    async def login(
        self, db: AsyncSession, email: str, password: str
    ) -> tuple[str, str]:
        user = await self.authenticate(db, email, password)
        return await self.issue_tokens(db, user.id)

    async def rotate_refresh(
        self, db: AsyncSession, refresh_token: str
    ) -> tuple[str, str]:
        token_hash = hash_token(refresh_token)
        record = await self.refresh_repo.get_by_hash(db, token_hash)
        if (
            record is None
            or record.revoked_at is not None
            or record.expires_at < _utc_now()
        ):
            raise InvalidTokenError()
        # Rotate: revoke the presented token before minting its replacement.
        await self.refresh_repo.revoke(db, token_hash, _utc_now())
        return await self.issue_tokens(db, record.user_id)

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        await self.refresh_repo.revoke(db, hash_token(refresh_token), _utc_now())
