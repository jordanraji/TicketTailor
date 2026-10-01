"""Recipient resolution + message hydration for the relay's fan-out (ADR-0016).

Maps one outbox row to the list of per-recipient messages the worker consumes.
Non-notification event types resolve to an empty list (the relay marks them
published without emitting). Recipient resolution goes through the api service
interfaces, never direct cross-module table reads.
"""

from __future__ import annotations

import logging
import uuid
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from tickettailor.events.models import Event
from tickettailor.events.service import EventService
from tickettailor.rsvp.service import RsvpService
from tickettailor.shared.exceptions import EventNotFoundError
from tickettailor.shared.models import OutboxEvent, OutboxEventType
from tickettailor.users.schemas import RecipientContact
from tickettailor.users.service import ClubFollowService, UserService

from relay.contract import (
    DomainEvent,
    NotificationPayload,
    PushSubscriptionKeys,
    PushSubscriptionSchema,
    RecipientSchema,
)

logger = logging.getLogger("relay.fanout")

# Event types that fan out to recipients. Everything else (event_created,
# rsvp_cancelled, club_membership_changed) is durable audit only (ADR-0016).
NOTIFICATION_EVENT_TYPES = frozenset(
    {
        OutboxEventType.visibility_changed,
        OutboxEventType.event_updated,
        OutboxEventType.rsvp_placed,
    }
)


class NotificationFanout:
    """Builds the hydrated, per-recipient messages for a notification outbox row."""

    def __init__(self) -> None:
        self.event_service = EventService()
        self.user_service = UserService()
        self.follow_service = ClubFollowService()
        self.rsvp_service = RsvpService()

    async def messages_for(
        self, db: AsyncSession, row: OutboxEvent
    ) -> list[DomainEvent]:
        """Resolve recipients and hydrate one message per recipient.

        Returns ``[]`` for non-notification rows, rows with no recipients, or
        rows whose event has since been deleted - in every case the caller marks
        the row published without emitting.
        """
        if row.event_type not in NOTIFICATION_EVENT_TYPES:
            return []

        recipient_ids = await self._recipients_for(db, row)
        if not recipient_ids:
            return []

        event_id = uuid.UUID(str(row.payload["event_id"]))
        try:
            event = await self.event_service.get_event_by_id(db, event_id)
        except EventNotFoundError:
            logger.warning(
                "outbox row %s references missing event %s; skipping fan-out",
                row.id,
                event_id,
            )
            return []

        contacts = await self.user_service.contact_details_for(db, recipient_ids)
        return [self._build_message(row, event, contact) for contact in contacts]

    async def _recipients_for(
        self, db: AsyncSession, row: OutboxEvent
    ) -> list[uuid.UUID]:
        # The api package is untyped to the relay (ignore_missing_imports), so
        # these service calls read as Any; cast back to the documented type.
        if row.event_type == OutboxEventType.visibility_changed:
            club_id = uuid.UUID(str(row.payload["club_id"]))
            return cast(
                list[uuid.UUID],
                await self.follow_service.followers_for_club(db, club_id),
            )
        if row.event_type == OutboxEventType.event_updated:
            event_id = uuid.UUID(str(row.payload["event_id"]))
            return cast(
                list[uuid.UUID],
                await self.rsvp_service.attendees_for_event(db, event_id),
            )
        # rsvp_placed: confirmation back to the attendee who RSVP'd.
        return [uuid.UUID(str(row.payload["user_id"]))]

    def _build_message(
        self, row: OutboxEvent, event: Event, contact: RecipientContact
    ) -> DomainEvent:
        push: PushSubscriptionSchema | None = None
        if contact.push_subscription is not None:
            push = PushSubscriptionSchema(
                endpoint=contact.push_subscription.endpoint,
                keys=PushSubscriptionKeys(
                    p256dh=contact.push_subscription.p256dh,
                    auth=contact.push_subscription.auth,
                ),
            )
        return DomainEvent(
            id=f"{row.id}:{contact.user_id}:0",
            event_type=str(row.event_type),
            aggregate_id=str(event.id),
            payload=NotificationPayload(
                event_title=event.title,
                recipient=RecipientSchema(
                    email=contact.email,
                    display_name=contact.display_name,
                    push_subscription=push,
                ),
            ),
        )
