import base64
import binascii
import json
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.events.cache import EventGeoCache
from tickettailor.events.models import Event, EventVisibility
from tickettailor.events.repositories import EventRepository
from tickettailor.events.schemas import EventCreate, EventUpdate
from tickettailor.organisers.service import ClubMembershipService, ClubService
from tickettailor.shared.app_services import app_services
from tickettailor.shared.exceptions import (
    ClubNotFoundError,
    EventNotFoundError,
    InvalidCursorError,
    NotClubMemberError,
    NotClubOrganiserError,
)
from tickettailor.shared.models import OutboxEvent, OutboxEventType

__all__ = ["EventService", "EventVisibility"]


class EventService:
    # SD-05: the browse-events handler clamps radius_m to this ceiling.
    MAX_RADIUS_M = 50_000

    def __init__(self) -> None:
        self.event_repo = EventRepository()
        self.club_service = ClubService()
        self.membership_service = ClubMembershipService()
        self.cache = EventGeoCache(app_services.get_redis().client)

    async def create_event(
        self,
        db: AsyncSession,
        body: EventCreate,
        creator_id: uuid.UUID,
    ) -> Event:
        try:
            await self.club_service.get_club_by_id(db, body.club_id)
        except ClubNotFoundError:
            raise

        await self._require_event_manager(
            db,
            user_id=creator_id,
            club_id=body.club_id,
        )

        event = await self.event_repo.create(
            db,
            club_id=body.club_id,
            created_by=creator_id,
            title=body.title,
            category=body.category,
            latitude=body.latitude,
            longitude=body.longitude,
            starts_at=body.starts_at,
            is_free=body.is_free,
            price=body.price,
            visibility=body.visibility,
            transition_at=body.transition_at,
            image_s3_key=body.image_s3_key,
        )
        self._add_outbox_event(
            db,
            event=event,
            event_type=OutboxEventType.event_created,
            user_id=creator_id,
        )
        return event

    async def get_event_by_id(self, db: AsyncSession, event_id: uuid.UUID) -> Event:
        event = await self.event_repo.get_by_id(db, event_id)
        if not event:
            raise EventNotFoundError()
        return event

    async def get_events_by_ids(
        self, db: AsyncSession, event_ids: list[uuid.UUID]
    ) -> list[Event]:
        return await self.event_repo.get_by_ids(db, event_ids)

    async def get_event_for_user(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> Event:
        event = await self.get_event_by_id(db, event_id)
        await self._require_event_viewer(db, user_id=user_id, event=event)
        return event

    async def list_events(
        self,
        db: AsyncSession,
        user_id: uuid.UUID | None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[Event], str | None]:
        cursor_starts_at, cursor_id = self._decode_cursor(cursor)
        visible_events: list[Event] = []

        while len(visible_events) <= limit:
            events = await self.event_repo.list_after(
                db,
                limit=limit + 1,
                cursor_starts_at=cursor_starts_at,
                cursor_id=cursor_id,
            )
            if not events:
                break

            for event in events:
                if await self._can_view_event(db, user_id=user_id, event=event):
                    visible_events.append(event)
                    if len(visible_events) > limit:
                        break

            if len(visible_events) > limit or len(events) <= limit:
                break

            last_event = events[-1]
            cursor_starts_at = last_event.starts_at
            cursor_id = last_event.id

        page_items = visible_events[:limit]
        next_cursor = None
        if len(visible_events) > limit:
            next_cursor = self._encode_cursor(page_items[-1])

        return page_items, next_cursor

    async def search_events_by_location(
        self,
        db: AsyncSession,
        latitude: Decimal,
        longitude: Decimal,
        radius_m: int,
        limit: int = 100,
        category: str | None = None,
    ) -> list[tuple[Event, float]]:
        """Geo-radius browse for the public map (FR2, SD-05).

        Returns public events within ``radius_m`` metres of the point (clamped
        to ``MAX_RADIUS_M``), nearest first, each paired with its distance in
        metres. The public map shows public events only; club-only events are
        discovered through their club, not the geo map, so no per-event
        membership check is needed here. Intended to run against the read
        replica (ADR-0008).
        """
        effective_radius = float(min(radius_m, self.MAX_RADIUS_M))

        cache_key = self.cache.build_key(
            latitude=latitude,
            longitude=longitude,
            radius_m=effective_radius,
            limit=limit,
            category=category,
        )
        cached_pairs = await self.cache.get(cache_key)

        if cached_pairs is not None:
            if not cached_pairs:
                return []
            try:
                event_ids = [eid for eid, _ in cached_pairs]
                events = await self.event_repo.get_by_ids(db, event_ids)
                event_map = {event.id: event for event in events}

                # Maintain original sorted order based on cached distance
                results = []
                for eid, dist in cached_pairs:
                    ev = event_map.get(eid)
                    if ev is not None and ev.visibility == EventVisibility.public:
                        results.append((ev, dist))
                return results
            except Exception:  # nosec B110
                pass

        db_results = await self.event_repo.search_within_radius(
            db,
            latitude=latitude,
            longitude=longitude,
            radius_m=effective_radius,
            limit=limit,
            category=category,
            visibility=EventVisibility.public,
        )

        try:
            cache_payload = [(ev.id, dist) for ev, dist in db_results]
            await self.cache.set(cache_key, cache_payload)
        except Exception:  # nosec B110
            pass

        return db_results

    async def update_event(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
        body: EventUpdate,
        user_id: uuid.UUID,
    ) -> Event:
        event = await self.get_event_by_id(db, event_id)
        await self._require_event_manager(db, user_id=user_id, club_id=event.club_id)

        fields_set = body.model_fields_set
        updated_event = await self.event_repo.update(
            db,
            event,
            title=body.title,
            category=body.category,
            category_was_set="category" in fields_set,
            latitude=body.latitude,
            longitude=body.longitude,
            starts_at=body.starts_at,
            is_free=body.is_free,
            price=body.price,
            price_was_set="price" in fields_set,
            visibility=body.visibility,
            transition_at=body.transition_at,
            transition_at_was_set="transition_at" in fields_set,
            image_s3_key=body.image_s3_key,
            image_s3_key_was_set="image_s3_key" in fields_set,
        )
        self._add_outbox_event(
            db,
            event=updated_event,
            event_type=OutboxEventType.event_updated,
            user_id=user_id,
        )
        return updated_event

    async def delete_event(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        event = await self.get_event_by_id(db, event_id)
        await self._require_event_manager(db, user_id=user_id, club_id=event.club_id)

        deleted = await self.event_repo.delete(db, event_id)
        if not deleted:
            raise EventNotFoundError()

    def _encode_cursor(self, event: Event) -> str:
        payload = {
            "starts_at": event.starts_at.isoformat(),
            "id": str(event.id),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode()

    def _decode_cursor(
        self, cursor: str | None
    ) -> tuple[datetime | None, uuid.UUID | None]:
        if cursor is None:
            return None, None

        try:
            decoded = base64.urlsafe_b64decode(cursor.encode())
            payload = json.loads(decoded)
            return datetime.fromisoformat(payload["starts_at"]), uuid.UUID(
                payload["id"]
            )
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError):
            raise InvalidCursorError() from None

    def _add_outbox_event(
        self,
        db: AsyncSession,
        event: Event,
        event_type: OutboxEventType,
        user_id: uuid.UUID,
    ) -> None:
        db.add(
            OutboxEvent(
                aggregate_id=event.id,
                event_type=event_type,
                payload={
                    "event_id": str(event.id),
                    "club_id": str(event.club_id),
                    "user_id": str(user_id),
                },
            )
        )

    async def _require_event_manager(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        club_id: uuid.UUID,
    ) -> None:
        can_manage_events = await self.membership_service.can_manage_events(
            db,
            user_id=user_id,
            club_id=club_id,
        )
        if not can_manage_events:
            raise NotClubOrganiserError()

    async def _can_view_event(
        self,
        db: AsyncSession,
        user_id: uuid.UUID | None,
        event: Event,
    ) -> bool:
        if event.visibility == EventVisibility.public:
            return True

        # Club-only events are never visible to an anonymous caller; otherwise
        # they are gated on club membership.
        if user_id is None:
            return False

        return await self.membership_service.is_member_of(
            db,
            user_id=user_id,
            club_id=event.club_id,
        )

    async def _require_event_viewer(
        self,
        db: AsyncSession,
        user_id: uuid.UUID | None,
        event: Event,
    ) -> None:
        if not await self._can_view_event(db, user_id=user_id, event=event):
            raise NotClubMemberError()
