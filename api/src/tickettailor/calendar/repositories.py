import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.calendar.models import CalendarToken


class CalendarTokenRepository:
    async def get_by_token(self, db: AsyncSession, token: str) -> CalendarToken | None:
        """Retrieve an active (non-revoked) CalendarToken by its token value."""
        stmt = select(CalendarToken).where(
            CalendarToken.token == token,
            CalendarToken.revoked_at.is_(None),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> CalendarToken | None:
        """Retrieve an active (non-revoked) CalendarToken for a specific user."""
        stmt = select(CalendarToken).where(
            CalendarToken.user_id == user_id,
            CalendarToken.revoked_at.is_(None),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, user_id: uuid.UUID, token: str
    ) -> CalendarToken:
        """Create a new CalendarToken for a user."""
        calendar_token = CalendarToken(user_id=user_id, token=token)
        db.add(calendar_token)
        await db.flush()
        return calendar_token

    async def revoke_by_user_id(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Revoke all active CalendarTokens for a specific user."""
        stmt = (
            update(CalendarToken)
            .where(
                CalendarToken.user_id == user_id,
                CalendarToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await db.execute(stmt)
