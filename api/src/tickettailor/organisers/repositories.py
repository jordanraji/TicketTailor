import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.organisers.models import Club, ClubMembership, MembershipRole


class ClubRepository:
    async def create(
        self,
        db: AsyncSession,
        name: str,
        description: str | None = None,
    ) -> Club:
        club = Club(name=name, description=description)
        db.add(club)
        await db.flush()
        return club

    async def get_by_id(self, db: AsyncSession, club_id: uuid.UUID) -> Club | None:
        result = await db.execute(select(Club).where(Club.id == club_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, db: AsyncSession, name: str) -> Club | None:
        result = await db.execute(select(Club).where(Club.name == name))
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        club_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Club | None:
        stmt = update(Club).where(Club.id == club_id)
        values = {}
        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description

        if not values:
            return await self.get_by_id(db, club_id)

        stmt = stmt.values(**values).execution_options(synchronize_session="fetch")
        await db.execute(stmt)
        return await self.get_by_id(db, club_id)

    async def list_clubs(self, db: AsyncSession) -> list[Club]:
        result = await db.execute(select(Club).order_by(Club.created_at.desc()))
        return list(result.scalars().all())


class ClubMembershipRepository:
    async def create(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        club_id: uuid.UUID,
        role: MembershipRole = MembershipRole.committee_member,
    ) -> ClubMembership:
        membership = ClubMembership(
            user_id=user_id,
            club_id=club_id,
            role=role,
        )
        db.add(membership)
        await db.flush()
        return membership

    async def get_by_id(
        self, db: AsyncSession, membership_id: uuid.UUID
    ) -> ClubMembership | None:
        result = await db.execute(
            select(ClubMembership).where(ClubMembership.id == membership_id)
        )
        return result.scalar_one_or_none()

    async def get_membership(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> ClubMembership | None:
        result = await db.execute(
            select(ClubMembership).where(
                ClubMembership.user_id == user_id,
                ClubMembership.club_id == club_id,
            )
        )
        return result.scalar_one_or_none()

    async def is_member_of(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        club_id: uuid.UUID,
        roles: Sequence[MembershipRole] | None = None,
    ) -> bool:
        stmt = select(ClubMembership.id).where(
            ClubMembership.user_id == user_id,
            ClubMembership.club_id == club_id,
        )
        if roles is not None:
            stmt = stmt.where(ClubMembership.role.in_(roles))
        result = await db.execute(stmt)
        return result.first() is not None

    async def remove_membership(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> bool:
        stmt = delete(ClubMembership).where(
            ClubMembership.user_id == user_id,
            ClubMembership.club_id == club_id,
        )
        result = await db.execute(stmt)
        return bool(cast(CursorResult[Any], result).rowcount > 0)

    async def get_clubs_for_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[Club]:
        """Clubs the user is a member of, newest first."""
        stmt = (
            select(Club)
            .join(ClubMembership, ClubMembership.club_id == Club.id)
            .where(ClubMembership.user_id == user_id)
            .order_by(Club.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_clubs_with_role_for_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[tuple[Club, MembershipRole]]:
        """Clubs the user is a member of paired with their role, in one query."""
        stmt = (
            select(Club, ClubMembership.role)
            .join(ClubMembership, ClubMembership.club_id == Club.id)
            .where(ClubMembership.user_id == user_id)
            .order_by(Club.created_at.desc())
        )
        result = await db.execute(stmt)
        return [(club, role) for club, role in result.all()]
