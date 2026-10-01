"""Service-level test for ``RsvpService.attendees_for_event`` (ADR-0016 fan-out)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.rsvp.models import Rsvp
from tickettailor.rsvp.service import RsvpService

pytestmark = pytest.mark.asyncio


async def test_attendees_for_event_returns_rsvping_users(
    db_session: AsyncSession,
) -> None:
    event_a, event_b = uuid.uuid4(), uuid.uuid4()
    u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db_session.add_all(
        [
            Rsvp(user_id=u1, event_id=event_a),
            Rsvp(user_id=u2, event_id=event_a),
            Rsvp(user_id=u3, event_id=event_b),
        ]
    )
    await db_session.flush()

    attendees = await RsvpService().attendees_for_event(db_session, event_a)
    assert set(attendees) == {u1, u2}


async def test_attendees_for_event_empty_when_none(
    db_session: AsyncSession,
) -> None:
    attendees = await RsvpService().attendees_for_event(db_session, uuid.uuid4())
    assert attendees == []
