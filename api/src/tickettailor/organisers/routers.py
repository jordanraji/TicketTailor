import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.organisers.schemas import (
    ClubCreate,
    ClubMembershipCreate,
    ClubMembershipResponse,
    ClubResponse,
    ClubUpdate,
    ClubWithMembershipResponse,
)
from tickettailor.organisers.service import ClubMembershipService, ClubService
from tickettailor.shared.app_services import get_db_session
from tickettailor.shared.logging import logger
from tickettailor.shared.security import require_current_user_id

router = APIRouter(prefix="/clubs", tags=["clubs"])


# NOTE: the literal "/my-clubs" routes are declared before "/{id}" so the path
# segment "my-clubs" is not matched against the UUID converter for "/{id}".
@router.get("", response_model=list[ClubResponse])
async def list_clubs(
    db: AsyncSession = Depends(get_db_session),
) -> list[ClubResponse]:
    clubs = await ClubService().list_clubs(db)
    return [ClubResponse.model_validate(club) for club in clubs]


@router.get("/my-clubs", response_model=list[ClubResponse])
async def get_user_clubs(
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[ClubResponse]:
    logger.info(f"Retrieving clubs for user: {user_id}")
    clubs = await ClubMembershipService().get_clubs_for_user(db, user_id)
    return [ClubResponse.model_validate(club) for club in clubs]


@router.get(
    "/my-clubs/with-membership", response_model=list[ClubWithMembershipResponse]
)
async def get_user_clubs_with_membership(
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[ClubWithMembershipResponse]:
    logger.info(f"Retrieving clubs with membership for user: {user_id}")
    clubs_with_role = await ClubMembershipService().get_clubs_with_role_for_user(
        db, user_id
    )
    return [
        ClubWithMembershipResponse(
            id=club.id,
            name=club.name,
            description=club.description,
            created_at=club.created_at,
            user_role=role,
        )
        for club, role in clubs_with_role
    ]


@router.post("", response_model=ClubResponse, status_code=status.HTTP_201_CREATED)
async def create_club(
    body: ClubCreate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> ClubResponse:
    logger.info(f"User {user_id} requesting to create club: {body.name}")
    club_service = ClubService()
    club = await club_service.create_club(
        db, name=body.name, description=body.description, creator_id=user_id
    )
    return ClubResponse.model_validate(club)


@router.get("/{id}", response_model=ClubResponse)
async def get_club(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ClubResponse:
    logger.info(f"Retrieving club: {id}")
    club_service = ClubService()
    club = await club_service.get_club_by_id(db, id)
    return ClubResponse.model_validate(club)


@router.put("/{id}", response_model=ClubResponse)
async def update_club(
    id: uuid.UUID,
    body: ClubUpdate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> ClubResponse:
    logger.info(f"User {user_id} requesting to update club: {id}")
    club_service = ClubService()
    club = await club_service.update_club(
        db,
        club_id=id,
        name=body.name,
        description=body.description,
        user_id=user_id,
    )
    return ClubResponse.model_validate(club)


@router.post(
    "/{id}/members",
    response_model=ClubMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    id: uuid.UUID,
    body: ClubMembershipCreate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> ClubMembershipResponse:
    logger.info(
        f"User {user_id} requesting to add user {body.user_id} "
        f"as {body.role} in club {id}"
    )
    membership_service = ClubMembershipService()
    membership = await membership_service.add_member(
        db,
        club_id=id,
        target_user_id=body.user_id,
        role=body.role,
        caller_user_id=user_id,
    )
    return ClubMembershipResponse.model_validate(membership)
