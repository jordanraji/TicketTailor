import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.organisers.models import Club, ClubMembership, MembershipRole
from tickettailor.organisers.repositories import (
    ClubMembershipRepository,
    ClubRepository,
)
from tickettailor.shared.exceptions import (
    AlreadyClubMemberError,
    ClubAlreadyExistsError,
    ClubNotFoundError,
    MembershipNotFoundError,
    NotClubAdminError,
)


class ClubService:
    def __init__(self) -> None:
        self.club_repo = ClubRepository()
        self.membership_repo = ClubMembershipRepository()

    async def create_club(
        self,
        db: AsyncSession,
        name: str,
        description: str | None,
        creator_id: uuid.UUID,
    ) -> Club:
        existing = await self.club_repo.get_by_name(db, name)
        if existing:
            raise ClubAlreadyExistsError(name)

        club = await self.club_repo.create(db, name, description)
        await self.membership_repo.create(
            db,
            user_id=creator_id,
            club_id=club.id,
            role=MembershipRole.admin,
        )
        return club

    async def get_club_by_id(self, db: AsyncSession, club_id: uuid.UUID) -> Club:
        club = await self.club_repo.get_by_id(db, club_id)
        if not club:
            raise ClubNotFoundError()
        return club

    async def update_club(
        self,
        db: AsyncSession,
        club_id: uuid.UUID,
        name: str | None,
        description: str | None,
        user_id: uuid.UUID,
    ) -> Club:
        club = await self.club_repo.get_by_id(db, club_id)
        if not club:
            raise ClubNotFoundError()

        is_admin = await self.membership_repo.is_member_of(
            db,
            user_id=user_id,
            club_id=club_id,
            roles=[MembershipRole.admin],
        )
        if not is_admin:
            raise NotClubAdminError()

        if name is not None and name != club.name:
            existing = await self.club_repo.get_by_name(db, name)
            if existing:
                raise ClubAlreadyExistsError(name)

        updated = await self.club_repo.update(
            db, club_id, name=name, description=description
        )
        if not updated:
            raise ClubNotFoundError()
        return updated

    async def list_clubs(self, db: AsyncSession) -> list[Club]:
        return await self.club_repo.list_clubs(db)


class ClubMembershipService:
    def __init__(self) -> None:
        self.club_repo = ClubRepository()
        self.membership_repo = ClubMembershipRepository()

    async def add_member(
        self,
        db: AsyncSession,
        club_id: uuid.UUID,
        target_user_id: uuid.UUID,
        role: MembershipRole,
        caller_user_id: uuid.UUID,
    ) -> ClubMembership:
        club = await self.club_repo.get_by_id(db, club_id)
        if not club:
            raise ClubNotFoundError()

        is_admin = await self.membership_repo.is_member_of(
            db,
            user_id=caller_user_id,
            club_id=club_id,
            roles=[MembershipRole.admin],
        )
        if not is_admin:
            raise NotClubAdminError()

        existing = await self.membership_repo.get_membership(
            db, user_id=target_user_id, club_id=club_id
        )
        if existing:
            raise AlreadyClubMemberError()

        return await self.membership_repo.create(
            db, user_id=target_user_id, club_id=club_id, role=role
        )

    async def remove_member(
        self,
        db: AsyncSession,
        club_id: uuid.UUID,
        target_user_id: uuid.UUID,
        caller_user_id: uuid.UUID,
    ) -> None:
        club = await self.club_repo.get_by_id(db, club_id)
        if not club:
            raise ClubNotFoundError()

        is_admin = await self.membership_repo.is_member_of(
            db,
            user_id=caller_user_id,
            club_id=club_id,
            roles=[MembershipRole.admin],
        )
        if not is_admin and caller_user_id != target_user_id:
            raise NotClubAdminError()

        success = await self.membership_repo.remove_membership(
            db, user_id=target_user_id, club_id=club_id
        )
        if not success:
            raise MembershipNotFoundError()

    async def is_member_of(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        club_id: uuid.UUID,
        roles: Sequence[MembershipRole] | None = None,
    ) -> bool:
        return await self.membership_repo.is_member_of(db, user_id, club_id, roles)

    async def can_manage_events(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        club_id: uuid.UUID,
    ) -> bool:
        return await self.membership_repo.is_member_of(
            db,
            user_id=user_id,
            club_id=club_id,
            roles=[MembershipRole.admin, MembershipRole.committee_member],
        )

    async def get_clubs_for_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[Club]:
        """Clubs the user is a member of."""
        return await self.membership_repo.get_clubs_for_user(db, user_id)

    async def get_clubs_with_role_for_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[tuple[Club, MembershipRole]]:
        """Clubs the user is a member of, each paired with their role."""
        return await self.membership_repo.get_clubs_with_role_for_user(db, user_id)


async def club_exists_validator(db: AsyncSession, club_id: uuid.UUID) -> bool:
    """Check if a club exists (used by the users module follow/unfollow callback)."""
    try:
        await ClubService().get_club_by_id(db, club_id)
        return True
    except ClubNotFoundError:
        return False
