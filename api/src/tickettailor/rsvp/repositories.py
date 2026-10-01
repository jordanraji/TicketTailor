import uuid
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.rsvp.models import Rsvp


class RsvpRepository:
    async def create(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> Rsvp:
        """Create a new RSVP row for the given user and event."""
        rsvp = Rsvp(user_id=user_id, event_id=event_id)
        db.add(rsvp)
        await db.flush()
        return rsvp

    async def delete(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> bool:
        """Delete an RSVP row. Returns True if deleted, False if it did not exist."""
        stmt = delete(Rsvp).where(Rsvp.user_id == user_id, Rsvp.event_id == event_id)
        result = await db.execute(stmt)
        return bool(cast(CursorResult[Any], result).rowcount > 0)

    async def get_by_user_and_event(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> Rsvp | None:
        """Get a specific RSVP by user_id and event_id."""
        stmt = select(Rsvp).where(Rsvp.user_id == user_id, Rsvp.event_id == event_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_count_by_event(self, db: AsyncSession, event_id: uuid.UUID) -> int:
        """Get the count of RSVPs for a specific event from PostgreSQL."""
        stmt = select(func.count(Rsvp.id)).where(Rsvp.event_id == event_id)
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_events_rsvped_by_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Get all event IDs that the user has RSVP'd to."""
        stmt = select(Rsvp.event_id).where(Rsvp.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_attendees_by_event(
        self, db: AsyncSession, event_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Get all user IDs who have RSVP'd to a specific event."""
        stmt = select(Rsvp.user_id).where(Rsvp.event_id == event_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())
