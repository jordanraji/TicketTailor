"""The outbox relay's two-phase work loop (ADR-0006, ADR-0010)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tickettailor.events.models import Event, EventVisibility
from tickettailor.shared.models import OutboxEvent, OutboxEventType

from relay.contract import DomainEvent
from relay.fanout import NotificationFanout
from relay.publisher import Publisher

logger = logging.getLogger("relay.service")


class OutboxRelay:
    """Runs one tick of the relay: a scheduled visibility transition followed by
    an outbox publish pass. Each phase runs in its own transaction so a failure
    in one cannot poison the other (ADR-0010)."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        publisher: Publisher,
        *,
        fanout: NotificationFanout | None = None,
        publish_batch_size: int = 100,
        transition_batch_size: int = 100,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._publisher = publisher
        self._fanout = fanout or NotificationFanout()
        self._publish_batch_size = publish_batch_size
        self._transition_batch_size = transition_batch_size

    async def run_visibility_transition(
        self, *, now: datetime | None = None
    ) -> list[uuid.UUID]:
        """Flip due club-only events to public and write a ``visibility_changed``
        outbox row for each, atomically (FR5).

        Returns the ids of the events that were flipped on this call. Rows are
        locked ``FOR UPDATE SKIP LOCKED`` so concurrent replicas never double-flip.
        """
        now = now or datetime.now(UTC)
        async with self._sessionmaker() as session:
            due = (
                await session.execute(
                    select(Event.id, Event.club_id)
                    .where(Event.visibility == EventVisibility.club_only)
                    .where(Event.transition_at.is_not(None))
                    .where(Event.transition_at <= now)
                    .order_by(Event.transition_at)
                    .limit(self._transition_batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()

            if not due:
                return []

            event_ids = [row.id for row in due]
            await session.execute(
                update(Event)
                .where(Event.id.in_(event_ids))
                .values(visibility=EventVisibility.public)
            )
            for row in due:
                # event_id + club_id let the worker resolve the club's followers
                # and fan out the broad-base FR5 notification.
                session.add(
                    OutboxEvent(
                        aggregate_id=row.id,
                        event_type=OutboxEventType.visibility_changed,
                        payload={
                            "event_id": str(row.id),
                            "club_id": str(row.club_id),
                        },
                    )
                )
            await session.commit()

            logger.info("visibility transition flipped %d event(s)", len(event_ids))
            return event_ids

    async def publish_pending(self) -> int:
        """Drain unpublished outbox rows: fan notification rows out to one
        hydrated message per recipient and publish them; mark every drained row
        published (ADR-0006, ADR-0016).

        Routing (ADR-0016): visibility_changed / event_updated / rsvp_placed are
        resolved to recipients, hydrated, and fanned out; other event types are
        marked published without emitting (durable audit only).

        Per-row delivery is all-or-nothing: a notification row is stamped
        published_at only once *every* recipient message is accepted, so a
        partial failure leaves the row to be re-emitted next tick - the
        deterministic dedup key makes that safe. Rows are isolated from each
        other (a failing row never blocks the rest). FOR UPDATE SKIP LOCKED keeps
        replicas off each other's rows. Returns the number of rows drained.
        """
        async with self._sessionmaker() as session:
            rows = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.published_at.is_(None))
                        .order_by(OutboxEvent.created_at)
                        .limit(self._publish_batch_size)
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )

            if not rows:
                return 0

            published_at = datetime.now(UTC)
            drained = 0
            for row in rows:
                try:
                    messages = await self._fanout.messages_for(session, row)
                except Exception:
                    logger.exception(
                        "fan-out resolution failed for outbox row %s; "
                        "leaving it for retry",
                        row.id,
                    )
                    continue
                if await self._publish_all(row, messages):
                    row.published_at = published_at
                    drained += 1
            await session.commit()

            logger.info("drained %d of %d pending outbox row(s)", drained, len(rows))
            return drained

    async def _publish_all(self, row: OutboxEvent, messages: list[DomainEvent]) -> bool:
        """Publish every message for a row, all-or-nothing. Returns True if all
        succeeded (or there were none, e.g. a non-notification row)."""
        for message in messages:
            try:
                await self._publisher.publish(message)
            except Exception:
                logger.exception(
                    "failed to publish message %s for outbox row %s; "
                    "leaving row for retry",
                    message.id,
                    row.id,
                )
                return False
        return True

    async def tick(self) -> None:
        """Run both phases once. Each phase is isolated: a failure in the
        visibility transition must not starve the publish loop, and vice versa
        (ADR-0010)."""
        try:
            await self.run_visibility_transition()
        except Exception:
            logger.exception("visibility transition phase failed")
        try:
            await self.publish_pending()
        except Exception:
            logger.exception("outbox publish phase failed")
