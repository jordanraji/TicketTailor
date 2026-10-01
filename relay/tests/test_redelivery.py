"""QA3-outbox - the relay's at-least-once redelivery guarantee (ADR-0006).

`test_fanout.py` proves a partial fan-out failure leaves the outbox row
unpublished (all-or-nothing). This file proves the *other half*: that such a
row is redelivered on a later tick, and that the resulting at-least-once
duplicate is harmless because every message carries a deterministic id the
consumer dedupes on.

This is the in-process analogue of "the relay is killed mid-fan-out". A crash
between publishing a message and committing `published_at` leaves the same DB
state a publish failure does - the row stays `published_at IS NULL` - so a
transient publisher error is a faithful, deterministic stand-in for the crash.
The cross-process SQS → Lambda redelivery (true worker kill) is an AWS-runtime
property and is exercised by the load-test infrastructure, not here.

Tests run against the real testcontainers Postgres via the `sessionmaker` /
fan-out seed helpers shared with `test_fanout.py`.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tickettailor.events.models import Event, EventVisibility
from tickettailor.shared.models import OutboxEvent, OutboxEventType
from tickettailor.users.models import ClubFollow, User

from relay.contract import DomainEvent
from relay.service import OutboxRelay

pytestmark = pytest.mark.asyncio

SessionMaker = async_sessionmaker[AsyncSession]


# ── seed helpers (relay tests operate below the API) ──────────────────────────
async def _add_event(sm: SessionMaker, *, club_id: uuid.UUID) -> uuid.UUID:
    async with sm() as session:
        event = Event(
            club_id=club_id,
            created_by=uuid.uuid4(),
            title="Launch Party",
            location=WKTElement("POINT(153.0137 -27.4975)", srid=4326),
            starts_at=datetime.now(UTC) + timedelta(days=7),
            is_free=True,
            visibility=EventVisibility.public,
        )
        session.add(event)
        await session.commit()
        return event.id


async def _add_follower(sm: SessionMaker, club_id: uuid.UUID) -> uuid.UUID:
    async with sm() as session:
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            password_hash="x",
            display_name="Follower",
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        session.add(ClubFollow(user_id=user_id, club_id=club_id))
        await session.commit()
        return user_id


async def _add_visibility_outbox(
    sm: SessionMaker, *, event_id: uuid.UUID, club_id: uuid.UUID
) -> uuid.UUID:
    async with sm() as session:
        row = OutboxEvent(
            aggregate_id=event_id,
            event_type=OutboxEventType.visibility_changed,
            payload={"event_id": str(event_id), "club_id": str(club_id)},
        )
        session.add(row)
        await session.flush()
        row_id = row.id
        await session.commit()
        return row_id


async def _unpublished_count(sm: SessionMaker) -> int:
    async with sm() as session:
        result = await session.execute(
            select(OutboxEvent).where(OutboxEvent.published_at.is_(None))
        )
        return len(list(result.scalars().all()))


class _FlakyPublisher:
    """Records every publish *attempt*, and raises once on the ``fail_on``-th.

    ``attempts`` holds every id the relay tried to publish (including the failed
    one); ``delivered`` holds only the ids that were accepted. After the single
    induced failure the publisher behaves normally, so a retry tick succeeds.
    """

    def __init__(self, fail_on: int) -> None:
        self.fail_on = fail_on
        self.count = 0
        self.attempts: list[str] = []
        self.delivered: list[str] = []

    async def publish(self, message: DomainEvent) -> None:
        self.count += 1
        self.attempts.append(message.id)
        if self.count == self.fail_on:
            raise RuntimeError("bus rejected message")
        self.delivered.append(message.id)


async def test_interrupted_fanout_redelivers_on_next_tick(
    sessionmaker: SessionMaker,
) -> None:
    """A publish that fails mid-fan-out is redelivered, with the same id.

    One follower, so one message. The first tick's publish raises (the relay
    "dies" before committing), leaving the row unpublished; the second tick
    re-resolves the same recipient and republishes the identical message id,
    marking the row published. The notification is delivered - exactly the
    at-least-once guarantee ADR-0006 promises.
    """
    club_id = uuid.uuid4()
    event_id = await _add_event(sessionmaker, club_id=club_id)
    follower = await _add_follower(sessionmaker, club_id)
    row_id = await _add_visibility_outbox(
        sessionmaker, event_id=event_id, club_id=club_id
    )
    expected_id = f"{row_id}:{follower}:0"

    publisher = _FlakyPublisher(fail_on=1)
    relay = OutboxRelay(sessionmaker, publisher)

    # Tick 1: the only message fails → row stays pending, nothing delivered.
    assert await relay.publish_pending() == 0
    assert publisher.delivered == []
    assert await _unpublished_count(sessionmaker) == 1

    # Tick 2: the transient failure has cleared → redelivered and drained.
    assert await relay.publish_pending() == 1
    assert publisher.delivered == [expected_id]
    assert await _unpublished_count(sessionmaker) == 0

    # The id the consumer dedupes on is identical across the failed and the
    # successful attempt - so redelivery is safe.
    assert publisher.attempts == [expected_id, expected_id]


async def test_at_least_once_delivery_is_deduplicable_by_id(
    sessionmaker: SessionMaker,
) -> None:
    """Redelivery can re-send an already-delivered message; dedup by id absorbs it.

    Two followers → two messages. The first tick delivers one then fails on the
    second, so the whole row is retried (all-or-nothing). The retry re-sends
    *both*, including the one already delivered. The result is more deliveries
    than recipients (at-least-once), but the set of distinct ids is exactly the
    recipient set - so a consumer deduping on the id ends with one notification
    per follower.
    """
    club_id = uuid.uuid4()
    event_id = await _add_event(sessionmaker, club_id=club_id)
    follower_a = await _add_follower(sessionmaker, club_id)
    follower_b = await _add_follower(sessionmaker, club_id)
    row_id = await _add_visibility_outbox(
        sessionmaker, event_id=event_id, club_id=club_id
    )
    expected_ids = {f"{row_id}:{follower_a}:0", f"{row_id}:{follower_b}:0"}

    # Fail on the second message of the first pass: message #1 is delivered,
    # message #2 raises, so the row is left for retry.
    publisher = _FlakyPublisher(fail_on=2)
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 0  # row not drained
    assert await _unpublished_count(sessionmaker) == 1

    assert await relay.publish_pending() == 1  # redelivered and drained
    assert await _unpublished_count(sessionmaker) == 0

    # At-least-once: at least one message was delivered more than once...
    assert len(publisher.delivered) > len(set(publisher.delivered))
    # ...but dedup by id collapses the duplicates to exactly one per recipient.
    assert set(publisher.delivered) == expected_ids
