import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.shared.app_services import get_db_session
from tickettailor.shared.config import settings
from tickettailor.shared.logging import logger
from tickettailor.shared.security import require_current_user_id
from tickettailor.users.schemas import (
    ClubFollowResponse,
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    UserResponse,
    UserUpdate,
)
from tickettailor.users.service import (
    ClubFollowService,
    PushSubscriptionService,
    UserService,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/push/vapid-public-key")
async def get_vapid_public_key() -> dict[str, str]:
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.get("/{id}", response_model=UserResponse)
async def get_user_profile(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    # TODO: Require authenticated access and enforce self-or-admin visibility once
    # the auth module exposes real JWT claims and role checks.
    logger.info(f"Retrieving user profile: {id}")
    user_service = UserService()
    user = await user_service.get_user_by_id(db, id)
    return UserResponse.model_validate(user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    logger.info(f"Updating profile for user: {user_id}")
    user_service = UserService()
    user = await user_service.update_user_profile(
        db,
        user_id=user_id,
        email=update_data.email,
        password=update_data.password,
        display_name=update_data.display_name,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/follow/{club_id}",
    response_model=ClubFollowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def follow_club(
    club_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> ClubFollowResponse:
    logger.info(f"User {user_id} requested to follow club: {club_id}")
    follow_service = ClubFollowService()
    follow_record = await follow_service.follow_club(db, user_id, club_id)
    return ClubFollowResponse.model_validate(follow_record)


@router.delete("/follow/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_club(
    club_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    logger.info(f"User {user_id} requested to unfollow club: {club_id}")
    follow_service = ClubFollowService()
    await follow_service.unfollow_club(db, user_id, club_id)


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_push(
    subscription: PushSubscriptionCreate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> PushSubscriptionResponse:
    logger.info(f"User {user_id} registering push subscription")
    push_service = PushSubscriptionService()
    sub_record = await push_service.subscribe_push(
        db,
        user_id=user_id,
        endpoint=subscription.endpoint,
        p256dh=subscription.p256dh,
        auth=subscription.auth,
    )
    return PushSubscriptionResponse.model_validate(sub_record)


@router.delete("/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_push(
    endpoint: Annotated[str, Query(...)],
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    logger.info(f"User {user_id} unregistering push subscription")
    push_service = PushSubscriptionService()
    await push_service.unsubscribe_push(db, user_id, endpoint)
