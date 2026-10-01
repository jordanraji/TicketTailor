"""FR5 - scheduled club-only -> public transition (ADR-0010).

Asserts: due events flip and emit a ``visibility_changed`` outbox row in the same
transaction; not-yet-due / no-transition / already-public events are untouched;
the transition is idempotent across ticks; and concurrent replicas flip exactly
once (FOR UPDATE SKIP LOCKED).
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tickettailor.events.models import Event, EventVisibility
from tickettailor.shared.models import OutboxEvent, OutboxEventType

from relay.publisher import CollectingPublisher
from relay.service import OutboxRelay

pytestmark = pytest.mark.asyncio

SessionMaker = async_sessionmaker[AsyncSession]
MakeEvent = Callable[..., Awaitable[uuid.UUID]]


async def _visibility(sm: SessionMaker, event_id: uuid.UUID) -> EventVisibility:
    async with sm() as session:
        result = await session.execute(
            select(Event.visibility).where(Event.id == event_id)
        )
        return result.scalar_one()


async def _visibility_changed_rows(sm: SessionMaker) -> list[OutboxEvent]:
    async with sm() as session:
        result = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == OutboxEventType.visibility_changed
            )
        )
        return list(result.scalars().all())


async def test_due_event_flips_and_writes_outbox(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    event_id = await make_event(transition_offset=timedelta(minutes=-5))
    relay = OutboxRelay(sessionmaker, CollectingPublisher())

    flipped = await relay.run_visibility_transition()

    assert flipped == [event_id]
    assert await _visibility(sessionmaker, event_id) == EventVisibility.public
    rows = await _visibility_changed_rows(sessionmaker)
    assert len(rows) == 1
    assert rows[0].payload["event_id"] == str(event_id)
    assert "club_id" in rows[0].payload
    # Publishing is a separate phase; the transition only writes the row.
    assert rows[0].published_at is None


async def test_future_transition_does_not_flip(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    event_id = await make_event(transition_offset=timedelta(hours=2))
    relay = OutboxRelay(sessionmaker, CollectingPublisher())

    assert await relay.run_visibility_transition() == []
    assert await _visibility(sessionmaker, event_id) == EventVisibility.club_only
    assert await _visibility_changed_rows(sessionmaker) == []


async def test_event_without_transition_time_never_flips(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    event_id = await make_event(transition_offset=None)
    relay = OutboxRelay(sessionmaker, CollectingPublisher())

    assert await relay.run_visibility_transition() == []
    assert await _visibility(sessionmaker, event_id) == EventVisibility.club_only


async def test_already_public_event_is_untouched(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    # A public event with a past transition_at must not re-emit a transition.
    await make_event(
        visibility=EventVisibility.public,
        transition_offset=timedelta(minutes=-5),
    )
    relay = OutboxRelay(sessionmaker, CollectingPublisher())

    assert await relay.run_visibility_transition() == []
    assert await _visibility_changed_rows(sessionmaker) == []


async def test_transition_is_idempotent_across_ticks(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    event_id = await make_event(transition_offset=timedelta(minutes=-5))
    relay = OutboxRelay(sessionmaker, CollectingPublisher())

    assert await relay.run_visibility_transition() == [event_id]
    # A second tick finds nothing due - no duplicate flip, no duplicate row.
    assert await relay.run_visibility_transition() == []
    assert len(await _visibility_changed_rows(sessionmaker)) == 1


async def test_full_tick_flips_then_publishes(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    await make_event(transition_offset=timedelta(minutes=-5))
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    await relay.tick()

    rows = await _visibility_changed_rows(sessionmaker)
    assert len(rows) == 1
    # The transition row is drained by the publish phase in the same tick. This
    # event has no club followers, so it is marked published without emitting
    # (ADR-0016); end-to-end fan-out to a follower is covered in test_fanout.
    assert rows[0].published_at is not None
    assert publisher.messages == []


async def test_concurrent_replicas_flip_exactly_once(
    sessionmaker: SessionMaker, make_event: MakeEvent
) -> None:
    event_id = await make_event(transition_offset=timedelta(minutes=-5))
    relay_a = OutboxRelay(sessionmaker, CollectingPublisher())
    relay_b = OutboxRelay(sessionmaker, CollectingPublisher())

    results = await asyncio.gather(
        relay_a.run_visibility_transition(),
        relay_b.run_visibility_transition(),
    )

    flipped = [event_id for result in results for event_id in result]
    assert flipped == [event_id]  # exactly one replica flipped it
    assert len(await _visibility_changed_rows(sessionmaker)) == 1
