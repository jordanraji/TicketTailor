import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.auth.models import RefreshToken


class RefreshTokenRepository:
    async def create(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(token)
        await db.flush()
        return token

    async def get_by_hash(
        self, db: AsyncSession, token_hash: str
    ) -> RefreshToken | None:
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(
        self, db: AsyncSession, token_hash: str, revoked_at: datetime
    ) -> bool:
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .execution_options(synchronize_session="fetch")
        )
        result = await db.execute(stmt)
        return bool(cast(CursorResult[Any], result).rowcount > 0)
