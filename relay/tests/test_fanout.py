"""ADR-0016 - relay publish phase: routing + per-recipient fan-out.

Asserts: notification rows fan out one hydrated message per recipient with a
deterministic dedup id; the right recipient set per event type; non-notification
rows are marked published without emitting; recipients without a push
subscription get email-only; a missing event is skipped; and a partial fan-out
failure leaves the whole row unpublished for retry (all-or-nothing).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tickettailor.events.models import Event, EventVisibility
from tickettailor.rsvp.models import Rsvp
from tickettailor.shared.models import OutboxEvent, OutboxEventType
from tickettailor.users.models import ClubFollow, PushSubscription, User

from relay.contract import DomainEvent
from relay.publisher import CollectingPublisher
from relay.service import OutboxRelay

pytestmark = pytest.mark.asyncio

SessionMaker = async_sessionmaker[AsyncSession]


# ── seed helpers (relay tests operate below the API) ──────────────────────────
async def _add_event(
    sm: SessionMaker,
    *,
    club_id: uuid.UUID,
    title: str = "Concert",
    visibility: EventVisibility = EventVisibility.public,
    transition_offset: timedelta | None = None,
) -> uuid.UUID:
    transition_at = (
        datetime.now(UTC) + transition_offset if transition_offset is not None else None
    )
    async with sm() as session:
        event = Event(
            club_id=club_id,
            created_by=uuid.uuid4(),
            title=title,
            location=WKTElement("POINT(153.0137 -27.4975)", srid=4326),
            starts_at=datetime.now(UTC) + timedelta(days=7),
            is_free=True,
            visibility=visibility,
            transition_at=transition_at,
        )
        session.add(event)
        await session.commit()
        return event.id


async def _add_user(sm: SessionMaker, *, with_push: bool = True) -> uuid.UUID:
    async with sm() as session:
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            password_hash="x",
            display_name="Attendee",
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        if with_push:
            session.add(
                PushSubscription(
                    user_id=user_id,
                    endpoint=f"https://push/{uuid.uuid4()}",
                    p256dh="p256dh",
                    auth="auth",
                )
            )
        await session.commit()
        return user_id


async def _add_follow(sm: SessionMaker, club_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with sm() as session:
        session.add(ClubFollow(user_id=user_id, club_id=club_id))
        await session.commit()


async def _add_rsvp(sm: SessionMaker, event_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with sm() as session:
        session.add(Rsvp(user_id=user_id, event_id=event_id))
        await session.commit()


async def _add_outbox(
    sm: SessionMaker,
    event_type: OutboxEventType,
    payload: dict[str, str],
    *,
    aggregate_id: uuid.UUID | None = None,
    published: bool = False,
) -> uuid.UUID:
    async with sm() as session:
        row = OutboxEvent(
            aggregate_id=aggregate_id or uuid.uuid4(),
            event_type=event_type,
            payload=payload,
            published_at=datetime.now(UTC) if published else None,
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


class _FailOnNthPublisher:
    """Succeeds for every publish except the n-th, which raises."""

    def __init__(self, fail_on: int) -> None:
        self.fail_on = fail_on
        self.count = 0

    async def publish(self, message: DomainEvent) -> None:
        self.count += 1
        if self.count == self.fail_on:
            raise RuntimeError("bus rejected message")


# ── routing of non-notification / housekeeping rows ───────────────────────────
async def test_non_notification_row_marked_published_without_emit(
    sessionmaker: SessionMaker,
) -> None:
    await _add_outbox(
        sessionmaker,
        OutboxEventType.event_created,
        {"event_id": str(uuid.uuid4()), "club_id": str(uuid.uuid4())},
    )
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 1  # row drained
    assert publisher.messages == []  # nothing emitted
    assert await _unpublished_count(sessionmaker) == 0


async def test_empty_outbox_drains_nothing(sessionmaker: SessionMaker) -> None:
    relay = OutboxRelay(sessionmaker, CollectingPublisher())
    assert await relay.publish_pending() == 0


async def test_already_published_rows_are_skipped(
    sessionmaker: SessionMaker,
) -> None:
    await _add_outbox(
        sessionmaker,
        OutboxEventType.event_created,
        {"event_id": str(uuid.uuid4()), "club_id": str(uuid.uuid4())},
        published=True,
    )
    relay = OutboxRelay(sessionmaker, CollectingPublisher())
    assert await relay.publish_pending() == 0


async def test_respects_batch_size(sessionmaker: SessionMaker) -> None:
    for _ in range(3):
        await _add_outbox(
            sessionmaker,
            OutboxEventType.event_created,
            {"event_id": str(uuid.uuid4()), "club_id": str(uuid.uuid4())},
        )
    relay = OutboxRelay(sessionmaker, CollectingPublisher(), publish_batch_size=2)

    assert await relay.publish_pending() == 2
    assert await relay.publish_pending() == 1
    assert await relay.publish_pending() == 0


# ── fan-out per event type ────────────────────────────────────────────────────
async def test_visibility_changed_fans_out_to_club_followers(
    sessionmaker: SessionMaker,
) -> None:
    club_id = uuid.uuid4()
    event_id = await _add_event(sessionmaker, club_id=club_id, title="Big Show")
    follower_with_push = await _add_user(sessionmaker, with_push=True)
    follower_no_push = await _add_user(sessionmaker, with_push=False)
    await _add_follow(sessionmaker, club_id, follower_with_push)
    await _add_follow(sessionmaker, club_id, follower_no_push)
    # A follower of a *different* club must not be notified.
    await _add_follow(sessionmaker, uuid.uuid4(), await _add_user(sessionmaker))

    row_id = await _add_outbox(
        sessionmaker,
        OutboxEventType.visibility_changed,
        {"event_id": str(event_id), "club_id": str(club_id)},
        aggregate_id=event_id,
    )
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 1
    assert len(publisher.messages) == 2

    by_id = {m.id: m for m in publisher.messages}
    assert set(by_id) == {
        f"{row_id}:{follower_with_push}:0",
        f"{row_id}:{follower_no_push}:0",
    }
    for message in publisher.messages:
        assert message.event_type == "visibility_changed"
        assert message.aggregate_id == str(event_id)
        assert message.payload.event_title == "Big Show"
        assert message.payload.recipient.email is not None

    assert (
        by_id[f"{row_id}:{follower_with_push}:0"].payload.recipient.push_subscription
        is not None
    )
    assert (
        by_id[f"{row_id}:{follower_no_push}:0"].payload.recipient.push_subscription
        is None
    )
    assert await _unpublished_count(sessionmaker) == 0


async def test_rsvp_placed_notifies_only_the_attendee(
    sessionmaker: SessionMaker,
) -> None:
    event_id = await _add_event(sessionmaker, club_id=uuid.uuid4())
    attendee = await _add_user(sessionmaker)
    await _add_user(sessionmaker)  # someone else - must not be notified

    row_id = await _add_outbox(
        sessionmaker,
        OutboxEventType.rsvp_placed,
        {
            "rsvp_id": str(uuid.uuid4()),
            "user_id": str(attendee),
            "event_id": str(event_id),
        },
        aggregate_id=event_id,
    )
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 1
    assert len(publisher.messages) == 1
    assert publisher.messages[0].id == f"{row_id}:{attendee}:0"


async def test_event_updated_notifies_rsvped_attendees(
    sessionmaker: SessionMaker,
) -> None:
    event_id = await _add_event(sessionmaker, club_id=uuid.uuid4())
    a1 = await _add_user(sessionmaker)
    a2 = await _add_user(sessionmaker)
    await _add_user(sessionmaker)  # not RSVP'd - excluded
    await _add_rsvp(sessionmaker, event_id, a1)
    await _add_rsvp(sessionmaker, event_id, a2)

    row_id = await _add_outbox(
        sessionmaker,
        OutboxEventType.event_updated,
        {
            "event_id": str(event_id),
            "club_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
        },
        aggregate_id=event_id,
    )
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 1
    assert {m.id for m in publisher.messages} == {
        f"{row_id}:{a1}:0",
        f"{row_id}:{a2}:0",
    }


async def test_visibility_changed_with_no_followers_marked_published(
    sessionmaker: SessionMaker,
) -> None:
    event_id = await _add_event(sessionmaker, club_id=uuid.uuid4())
    await _add_outbox(
        sessionmaker,
        OutboxEventType.visibility_changed,
        {"event_id": str(event_id), "club_id": str(uuid.uuid4())},
        aggregate_id=event_id,
    )
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 1  # nothing to send, but drained
    assert publisher.messages == []
    assert await _unpublished_count(sessionmaker) == 0


async def test_missing_event_is_skipped_and_marked_published(
    sessionmaker: SessionMaker,
) -> None:
    club_id = uuid.uuid4()
    await _add_follow(sessionmaker, club_id, await _add_user(sessionmaker))
    # event_id references an event that does not exist.
    await _add_outbox(
        sessionmaker,
        OutboxEventType.visibility_changed,
        {"event_id": str(uuid.uuid4()), "club_id": str(club_id)},
    )
    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    assert await relay.publish_pending() == 1
    assert publisher.messages == []
    assert await _unpublished_count(sessionmaker) == 0


async def test_partial_fanout_failure_leaves_row_unpublished(
    sessionmaker: SessionMaker,
) -> None:
    club_id = uuid.uuid4()
    event_id = await _add_event(sessionmaker, club_id=club_id)
    await _add_follow(sessionmaker, club_id, await _add_user(sessionmaker))
    await _add_follow(sessionmaker, club_id, await _add_user(sessionmaker))
    await _add_outbox(
        sessionmaker,
        OutboxEventType.visibility_changed,
        {"event_id": str(event_id), "club_id": str(club_id)},
        aggregate_id=event_id,
    )

    # Fail on the second recipient - the row must stay unpublished (all-or-nothing).
    relay = OutboxRelay(sessionmaker, _FailOnNthPublisher(fail_on=2))

    assert await relay.publish_pending() == 0
    assert await _unpublished_count(sessionmaker) == 1


async def test_full_tick_transitions_then_fans_out(
    sessionmaker: SessionMaker,
) -> None:
    """End-to-end FR5: a due club-only event flips to public, and in the same
    tick the resulting visibility_changed row fans out to a club follower."""
    club_id = uuid.uuid4()
    event_id = await _add_event(
        sessionmaker,
        club_id=club_id,
        title="Gala",
        visibility=EventVisibility.club_only,
        transition_offset=timedelta(minutes=-5),
    )
    follower = await _add_user(sessionmaker)
    await _add_follow(sessionmaker, club_id, follower)

    publisher = CollectingPublisher()
    relay = OutboxRelay(sessionmaker, publisher)

    await relay.tick()

    async with sessionmaker() as session:
        visibility = (
            await session.execute(select(Event.visibility).where(Event.id == event_id))
        ).scalar_one()
    assert visibility == EventVisibility.public

    assert len(publisher.messages) == 1
    message = publisher.messages[0]
    assert message.event_type == "visibility_changed"
    assert message.aggregate_id == str(event_id)
    assert message.payload.event_title == "Gala"
    assert message.payload.recipient.email is not None
    assert await _unpublished_count(sessionmaker) == 0
