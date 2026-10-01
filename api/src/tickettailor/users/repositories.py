import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.users.models import ClubFollow, PushSubscription, User, UserRole


class UserRepository:
    async def create(
        self,
        db: AsyncSession,
        email: str,
        password_hash: str,
        display_name: str,
        role: UserRole = UserRole.student,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
        )
        db.add(user)
        await db.flush()
        return user

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        result = await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        email: str | None = None,
        password_hash: str | None = None,
        display_name: str | None = None,
    ) -> User | None:
        stmt = update(User).where(User.id == user_id, User.deleted_at.is_(None))
        values = {}
        if email is not None:
            values["email"] = email
        if password_hash is not None:
            values["password_hash"] = password_hash
        if display_name is not None:
            values["display_name"] = display_name

        if not values:
            return await self.get_by_id(db, user_id)

        stmt = stmt.values(**values).execution_options(synchronize_session="fetch")
        await db.execute(stmt)
        return await self.get_by_id(db, user_id)

    async def soft_delete(self, db: AsyncSession, user_id: uuid.UUID) -> bool:
        stmt = (
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
            .execution_options(synchronize_session="fetch")
        )
        result = await db.execute(stmt)
        return bool(cast(CursorResult[Any], result).rowcount > 0)

    async def get_by_ids(
        self, db: AsyncSession, user_ids: list[uuid.UUID]
    ) -> list[User]:
        """Batch-fetch live (non-deleted) users by id."""
        if not user_ids:
            return []
        result = await db.execute(
            select(User).where(User.id.in_(user_ids), User.deleted_at.is_(None))
        )
        return list(result.scalars().all())


class ClubFollowRepository:
    async def follow(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> ClubFollow:
        follow_record = ClubFollow(user_id=user_id, club_id=club_id)
        db.add(follow_record)
        await db.flush()
        return follow_record

    async def unfollow(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> bool:
        stmt = delete(ClubFollow).where(
            ClubFollow.user_id == user_id, ClubFollow.club_id == club_id
        )
        result = await db.execute(stmt)
        return bool(cast(CursorResult[Any], result).rowcount > 0)

    async def get_followed_clubs(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await db.execute(
            select(ClubFollow.club_id).where(ClubFollow.user_id == user_id)
        )
        return list(result.scalars().all())

    async def is_following(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> bool:
        result = await db.execute(
            select(ClubFollow.id).where(
                ClubFollow.user_id == user_id, ClubFollow.club_id == club_id
            )
        )
        return result.first() is not None

    async def get_followers_by_club(
        self, db: AsyncSession, club_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Get all user IDs following a club (reverse of get_followed_clubs)."""
        result = await db.execute(
            select(ClubFollow.user_id).where(ClubFollow.club_id == club_id)
        )
        return list(result.scalars().all())


class PushSubscriptionRepository:
    async def subscribe(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushSubscription:
        result = await db.execute(
            select(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.endpoint == endpoint,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.p256dh = p256dh
            existing.auth = auth
            await db.flush()
            return existing

        sub = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        )
        db.add(sub)
        await db.flush()
        return sub

    async def unsubscribe(
        self, db: AsyncSession, user_id: uuid.UUID, endpoint: str
    ) -> bool:
        stmt = delete(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
        result = await db.execute(stmt)
        return bool(cast(CursorResult[Any], result).rowcount > 0)

    async def get_subscriptions_by_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[PushSubscription]:
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_latest_by_users(
        self, db: AsyncSession, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, PushSubscription]:
        """Most recent push subscription per user, for the relay's fan-out
        (ADR-0016). Users with no subscription are absent from the result."""
        if not user_ids:
            return {}
        # DISTINCT ON (user_id) + ORDER BY created_at DESC = newest per user.
        stmt = (
            select(PushSubscription)
            .where(PushSubscription.user_id.in_(user_ids))
            .order_by(
                PushSubscription.user_id,
                PushSubscription.created_at.desc(),
            )
            .distinct(PushSubscription.user_id)
        )
        result = await db.execute(stmt)
        return {sub.user_id: sub for sub in result.scalars().all()}
