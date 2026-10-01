import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.calendar.schemas import CalendarTokenResponse
from tickettailor.calendar.service import CalendarService
from tickettailor.shared.app_services import get_db_session, get_replica_db_session
from tickettailor.shared.security import require_current_user_id

router = APIRouter(prefix="/calendar", tags=["calendar"])
router_events = APIRouter(prefix="/events", tags=["calendar"])


def _build_feed_url(request: Request, token: str) -> str:
    """Build the absolute feed URL using the Request object."""
    return str(request.url_for("get_user_feed", token=token))


@router.get("/token", response_model=CalendarTokenResponse)
async def get_calendar_token(
    request: Request,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> CalendarTokenResponse:
    """Retrieve the current active calendar feed token for the logged-in user."""
    token = await CalendarService().get_or_create_token(db, user_id)
    feed_url = _build_feed_url(request, token)
    return CalendarTokenResponse(token=token, feed_url=feed_url)


@router.post("/token/rotate", response_model=CalendarTokenResponse)
async def rotate_calendar_token(
    request: Request,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> CalendarTokenResponse:
    """Rotate the calendar feed token for the logged-in user, revoking the old one."""
    token = await CalendarService().rotate_token(db, user_id)
    feed_url = _build_feed_url(request, token)
    return CalendarTokenResponse(token=token, feed_url=feed_url)


@router.get("/feed/{token}", response_class=Response)
async def get_user_feed(
    token: str,
    db: AsyncSession = Depends(get_replica_db_session),
) -> Response:
    """Public subscription endpoint returning the user's multi-event calendar
    feed in iCal format.

    Uses the read replica database session.
    """
    ical_content = await CalendarService().get_user_feed_ical(db, token)
    return Response(
        content=ical_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=feed.ics",
        },
    )


@router_events.get("/{event_id}/calendar.ics", response_class=Response)
async def get_event_ical(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_replica_db_session),
) -> Response:
    """Download single event details in standard iCal format.

    Uses the read replica database session.
    """
    ical_content = await CalendarService().get_event_ical(
        db, user_id=user_id, event_id=event_id
    )
    return Response(
        content=ical_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=event-{event_id}.ics",
        },
    )
