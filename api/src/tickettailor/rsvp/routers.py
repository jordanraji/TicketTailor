import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.rsvp.schemas import RsvpResponse, RsvpStatusResponse
from tickettailor.rsvp.service import RsvpService
from tickettailor.shared.app_services import get_db_session
from tickettailor.shared.security import require_current_user_id

router = APIRouter(prefix="/events", tags=["rsvp"])


@router.post(
    "/{event_id}/rsvp",
    response_model=RsvpResponse,
    status_code=status.HTTP_201_CREATED,
)
async def place_rsvp(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> RsvpResponse:
    """Register the current user's RSVP for the specified event."""
    new_count = await RsvpService().place_rsvp(db, user_id=user_id, event_id=event_id)
    return RsvpResponse(attendee_count=new_count)


@router.delete(
    "/{event_id}/rsvp",
    response_model=RsvpResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_rsvp(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> RsvpResponse:
    """Cancel the current user's RSVP for the specified event."""
    new_count = await RsvpService().cancel_rsvp(db, user_id=user_id, event_id=event_id)
    return RsvpResponse(attendee_count=new_count)


@router.get(
    "/{event_id}/rsvp",
    response_model=RsvpStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_rsvp_status(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> RsvpStatusResponse:
    """Retrieve the current user's RSVP status for the specified event."""
    is_going, count = await RsvpService().get_rsvp_status(
        db, user_id=user_id, event_id=event_id
    )
    return RsvpStatusResponse(is_going=is_going, attendee_count=count)
