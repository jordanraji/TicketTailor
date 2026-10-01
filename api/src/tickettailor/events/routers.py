import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import AfterValidator
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.events.schemas import (
    EventCreate,
    EventListResponse,
    EventResponse,
    EventUpdate,
)
from tickettailor.events.service import EventService
from tickettailor.shared.app_services import get_db_session, get_replica_db_session
from tickettailor.shared.exceptions import IncompleteGeoFilterError
from tickettailor.shared.logging import logger
from tickettailor.shared.security import (
    optional_current_user_id,
    require_current_user_id,
)
from tickettailor.shared.validation import reject_unstorable_text_optional

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/hello")
async def hello_events() -> dict[str, str]:
    return {"message": "Hello from events module"}


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    logger.info(f"User {user_id} requesting to create event: {body.title}")
    event_service = EventService()
    event = await event_service.create_event(db, body=body, creator_id=user_id)
    return EventResponse.model_validate(event)


@router.get("", response_model=EventListResponse)
async def list_events(
    lat: Decimal | None = Query(None, ge=-90, le=90),
    lng: Decimal | None = Query(None, ge=-180, le=180),
    radius_m: int | None = Query(None, ge=1),
    category: Annotated[
        str | None,
        Query(max_length=100),
        AfterValidator(reject_unstorable_text_optional),
    ] = None,
    limit: int = Query(100, ge=1, le=100),
    cursor: str | None = Query(None),
    user_id: uuid.UUID | None = Depends(optional_current_user_id),
    db: AsyncSession = Depends(get_replica_db_session),
) -> EventListResponse:
    """List events (public browse; auth optional).

    With ``lat``/``lng``/``radius_m`` this is the public map's geo-radius browse
    (FR2, SD-05): public events within the radius, nearest first, each with its
    ``distance_m``. Without them it is the visibility-aware, cursor-paginated
    list. Anonymous callers see public events only; a signed-in caller also sees
    their club-only events. Reads route to the replica (ADR-0008).
    """
    event_service = EventService()

    if lat is not None or lng is not None or radius_m is not None:
        if lat is None or lng is None or radius_m is None:
            raise IncompleteGeoFilterError()
        results = await event_service.search_events_by_location(
            db,
            latitude=lat,
            longitude=lng,
            radius_m=radius_m,
            limit=limit,
            category=category,
        )
        items = []
        for event, distance_m in results:
            item = EventResponse.model_validate(event)
            item.distance_m = round(distance_m, 1)
            items.append(item)
        return EventListResponse(items=items, next_cursor=None)

    events, next_cursor = await event_service.list_events(
        db,
        user_id=user_id,
        limit=limit,
        cursor=cursor,
    )
    return EventListResponse(
        items=[EventResponse.model_validate(event) for event in events],
        next_cursor=next_cursor,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    user_id: uuid.UUID | None = Depends(optional_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    # Public browse: anonymous callers may read a public event (reached from the
    # landing page / map); a club-only event is withheld unless the caller is a
    # member (NotClubMemberError -> 403).
    event_service = EventService()
    event = await event_service.get_event_for_user(
        db,
        event_id=event_id,
        user_id=user_id,
    )
    return EventResponse.model_validate(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    logger.info(f"User {user_id} requesting to update event: {event_id}")
    event_service = EventService()
    event = await event_service.update_event(
        db,
        event_id=event_id,
        body=body,
        user_id=user_id,
    )
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    logger.info(f"User {user_id} requesting to delete event: {event_id}")
    event_service = EventService()
    await event_service.delete_event(db, event_id=event_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
