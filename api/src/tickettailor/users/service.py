import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.shared.club_validator import validate_club_exists
from tickettailor.shared.exceptions import (
    AlreadyFollowingError,
    ClubNotFoundError,
    FollowNotFoundError,
    SubscriptionNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from tickettailor.shared.security import hash_password
from tickettailor.users.models import ClubFollow, PushSubscription, User
from tickettailor.users.repositories import (
    ClubFollowRepository,
    PushSubscriptionRepository,
    UserRepository,
)
from tickettailor.users.schemas import RecipientContact, RecipientPushSubscription


class UserService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.sub_repo = PushSubscriptionRepository()

    async def register_user(
        self, db: AsyncSession, email: str, password: str, display_name: str
    ) -> User:
        existing_user = await self.user_repo.get_by_email(db, email)
        if existing_user:
            raise UserAlreadyExistsError(email)

        pwd_hash = hash_password(password)
        return await self.user_repo.create(db, email, pwd_hash, display_name)

    async def get_user_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def get_user_by_email(self, db: AsyncSession, email: str) -> User:
        user = await self.user_repo.get_by_email(db, email)
        if not user:
            raise UserNotFoundError()
        return user

    async def update_user_profile(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        email: str | None = None,
        password: str | None = None,
        display_name: str | None = None,
    ) -> User:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        pwd_hash = None
        if password is not None:
            pwd_hash = hash_password(password)

        if email is not None and email != user.email:
            existing = await self.user_repo.get_by_email(db, email)
            if existing:
                raise UserAlreadyExistsError(email)

        updated_user = await self.user_repo.update(
            db,
            user_id,
            email=email,
            password_hash=pwd_hash,
            display_name=display_name,
        )
        if not updated_user:
            raise UserNotFoundError()
        return updated_user

    async def delete_user(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        success = await self.user_repo.soft_delete(db, user_id)
        if not success:
            raise UserNotFoundError()

    async def contact_details_for(
        self, db: AsyncSession, user_ids: list[uuid.UUID]
    ) -> list[RecipientContact]:
        """Batch notification contact details for the given users (ADR-0016).

        Soft-deleted users are skipped. Each recipient carries their most recent
        push subscription, or None if they have none.
        """
        if not user_ids:
            return []

        users = await self.user_repo.get_by_ids(db, user_ids)
        latest_subs = await self.sub_repo.get_latest_by_users(db, user_ids)

        contacts: list[RecipientContact] = []
        for user in users:
            sub = latest_subs.get(user.id)
            contacts.append(
                RecipientContact(
                    user_id=user.id,
                    email=user.email,
                    display_name=user.display_name,
                    push_subscription=(
                        RecipientPushSubscription(
                            endpoint=sub.endpoint,
                            p256dh=sub.p256dh,
                            auth=sub.auth,
                        )
                        if sub is not None
                        else None
                    ),
                )
            )
        return contacts


class ClubFollowService:
    def __init__(self) -> None:
        self.follow_repo = ClubFollowRepository()
        self.user_repo = UserRepository()

    async def follow_club(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> ClubFollow:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        if not await validate_club_exists(db, club_id):
            raise ClubNotFoundError()

        is_following = await self.follow_repo.is_following(db, user_id, club_id)
        if is_following:
            raise AlreadyFollowingError()

        return await self.follow_repo.follow(db, user_id, club_id)

    async def unfollow_club(
        self, db: AsyncSession, user_id: uuid.UUID, club_id: uuid.UUID
    ) -> None:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        if not await validate_club_exists(db, club_id):
            raise ClubNotFoundError()

        success = await self.follow_repo.unfollow(db, user_id, club_id)
        if not success:
            raise FollowNotFoundError()

    async def get_clubs_followed_by_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        return await self.follow_repo.get_followed_clubs(db, user_id)

    async def followers_for_club(
        self, db: AsyncSession, club_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Return the user IDs following a club.

        Recipient set for the FR5 ``visibility_changed`` fan-out (ADR-0016)."""
        return await self.follow_repo.get_followers_by_club(db, club_id)


class PushSubscriptionService:
    def __init__(self) -> None:
        self.sub_repo = PushSubscriptionRepository()
        self.user_repo = UserRepository()

    async def subscribe_push(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushSubscription:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        return await self.sub_repo.subscribe(db, user_id, endpoint, p256dh, auth)

    async def unsubscribe_push(
        self, db: AsyncSession, user_id: uuid.UUID, endpoint: str
    ) -> None:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        success = await self.sub_repo.unsubscribe(db, user_id, endpoint)
        if not success:
            raise SubscriptionNotFoundError()

    async def get_subscriptions_by_user(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[PushSubscription]:
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise UserNotFoundError()

        return await self.sub_repo.get_subscriptions_by_user(db, user_id)
