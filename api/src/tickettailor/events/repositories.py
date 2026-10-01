import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from geoalchemy2.elements import WKTElement
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.events.models import Event, EventVisibility


def _location_from_coordinates(latitude: Decimal, longitude: Decimal) -> Any:
    return cast(
        Any,
        WKTElement(
            f"POINT({longitude} {latitude})",
            srid=4326,
        ),
    )


class EventRepository:
    async def create(
        self,
        db: AsyncSession,
        club_id: uuid.UUID,
        created_by: uuid.UUID,
        title: str,
        category: str | None,
        latitude: Decimal,
        longitude: Decimal,
        starts_at: datetime,
        is_free: bool,
        price: Decimal | None,
        visibility: EventVisibility,
        transition_at: datetime | None,
        image_s3_key: str | None,
    ) -> Event:
        event = Event(
            club_id=club_id,
            created_by=created_by,
            title=title,
            category=category,
            location=_location_from_coordinates(latitude, longitude),
            starts_at=starts_at,
            is_free=is_free,
            price=price,
            visibility=visibility,
            transition_at=transition_at,
            image_s3_key=image_s3_key,
        )
        db.add(event)
        await db.flush()
        return event

    async def get_by_id(self, db: AsyncSession, event_id: uuid.UUID) -> Event | None:
        result = await db.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def get_by_ids(
        self, db: AsyncSession, event_ids: list[uuid.UUID]
    ) -> list[Event]:
        if not event_ids:
            return []
        result = await db.execute(select(Event).where(Event.id.in_(event_ids)))
        return list(result.scalars().all())

    async def list_after(
        self,
        db: AsyncSession,
        limit: int,
        cursor_starts_at: datetime | None = None,
        cursor_id: uuid.UUID | None = None,
    ) -> list[Event]:
        query = select(Event).order_by(Event.starts_at, Event.id).limit(limit)

        if cursor_starts_at is not None and cursor_id is not None:
            query = query.where(
                or_(
                    Event.starts_at > cursor_starts_at,
                    and_(
                        Event.starts_at == cursor_starts_at,
                        Event.id > cursor_id,
                    ),
                )
            )

        result = await db.execute(query)
        return list(result.scalars().all())

    async def search_within_radius(
        self,
        db: AsyncSession,
        latitude: Decimal,
        longitude: Decimal,
        radius_m: float,
        limit: int,
        category: str | None = None,
        visibility: EventVisibility = EventVisibility.public,
    ) -> list[tuple[Event, float]]:
        """Return events within ``radius_m`` metres of the point, nearest first.

        Uses PostGIS ``ST_DWithin`` over the ``Geography`` column so the radius
        is in metres and the GiST index (`idx_events_location`) serves the
        filter (SD-05). ``ST_Distance`` yields the per-event distance for map
        markers. The point is bound via ``ST_GeogFromText`` (parameterised, not
        string-built SQL).
        """
        point = func.ST_GeogFromText(
            f"SRID=4326;POINT({float(longitude)} {float(latitude)})"
        )
        distance = func.ST_Distance(Event.location, point)
        query = (
            select(Event, distance.label("distance_m"))
            .where(func.ST_DWithin(Event.location, point, radius_m))
            .where(Event.visibility == visibility)
            .order_by(distance.asc())
            .limit(limit)
        )
        if category is not None:
            query = query.where(Event.category == category)

        result = await db.execute(query)
        return [(event, float(distance_m)) for event, distance_m in result.all()]

    async def update(
        self,
        db: AsyncSession,
        event: Event,
        title: str | None = None,
        category: str | None = None,
        category_was_set: bool = False,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        starts_at: datetime | None = None,
        is_free: bool | None = None,
        price: Decimal | None = None,
        price_was_set: bool = False,
        visibility: EventVisibility | None = None,
        transition_at: datetime | None = None,
        transition_at_was_set: bool = False,
        image_s3_key: str | None = None,
        image_s3_key_was_set: bool = False,
    ) -> Event:
        if title is not None:
            event.title = title
        if category_was_set:
            event.category = category
        if latitude is not None and longitude is not None:
            event.location = _location_from_coordinates(latitude, longitude)
        if starts_at is not None:
            event.starts_at = starts_at
        if is_free is not None:
            event.is_free = is_free
        if price_was_set:
            event.price = price
        if visibility is not None:
            event.visibility = visibility
        if transition_at_was_set:
            event.transition_at = transition_at
        if image_s3_key_was_set:
            event.image_s3_key = image_s3_key

        await db.flush()
        return event

    async def delete(self, db: AsyncSession, event_id: uuid.UUID) -> bool:
        result = await db.execute(delete(Event).where(Event.id == event_id))
        return bool(cast(CursorResult[Any], result).rowcount > 0)
