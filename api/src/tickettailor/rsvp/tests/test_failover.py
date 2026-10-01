"""QA3-failover: a primary-database failover mid-burst preserves the RSVP count.

This is the in-process analogue of an RDS primary failover (ADR-0008), in the
same spirit as the drift/reconcile cases in ``test_rsvp_reliability.py``: we
cannot promote a standby inside a single testcontainer, so we inject the
*failure mode* a failover produces - the primary becoming unreachable so that
in-flight writes are rejected and rolled back - and assert the count invariant
the design promises:

* committed RSVPs from before the outage survive it (no lost count);
* writes that were in-flight when the primary dropped fail cleanly and leave
  **no phantom increment** on the Redis counter (the write-through increment
  runs only after a successful insert, ADR-0005);
* once the standby is promoted (the outage lifts), retries land and the counter,
  the reported count, and the persisted rows reconcile to zero drift.

The real Multi-AZ promotion is a platform guarantee exercised against deployed
infra during a load run; this test pins the application-level invariant that
makes that promotion safe, and runs in CI against the testcontainer stack.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.rsvp.repositories import RsvpRepository
from tickettailor.rsvp.service import RsvpService

pytestmark = pytest.mark.asyncio


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    password = "password123"
    register_response = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Test User"},
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


async def _create_club(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post(
        "/clubs",
        json={"name": name, "description": "Failover fixtures"},
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _create_event(
    client: AsyncClient, headers: dict[str, str], club_id: str
) -> str:
    response = await client.post(
        "/events",
        json={
            "club_id": club_id,
            "title": "Failover Event",
            "latitude": "-27.4975",
            "longitude": "153.0137",
            "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "is_free": True,
            "visibility": "public",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _persisted_count(db_session: AsyncSession, event_id: str) -> int:
    return await RsvpService().rsvp_repo.get_count_by_event(
        db_session, uuid.UUID(event_id)
    )


async def _reported_count(
    client: AsyncClient, headers: dict[str, str], event_id: str
) -> int:
    resp = await client.get(f"/events/{event_id}/rsvp", headers=headers)
    assert resp.status_code == 200
    return cast(int, resp.json()["attendee_count"])


async def _primary_unreachable(*_args: object, **_kwargs: object) -> object:
    """Stand-in for ``RsvpRepository.create`` while the primary is down.

    asyncpg surfaces a dropped primary as an ``OperationalError``; the RSVP
    service only translates ``IntegrityError`` (-> 409), so this propagates and
    the request fails without ever reaching the counter increment.
    """
    raise OperationalError(
        "INSERT INTO rsvp.rsvps ...",
        {},
        Exception("server closed the connection unexpectedly (primary failover)"),
    )


async def test_primary_failover_midburst_preserves_count(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await _register(client, "failover-admin@example.com")
    club_id = await _create_club(client, admin, "Failover Club")
    event_id = await _create_event(client, admin, club_id)

    # Phase 0 - before the failover: P students RSVP and commit.
    p = 5
    committed = [
        await _register(client, f"failover-pre-{i}@example.com") for i in range(p)
    ]
    for headers in committed:
        resp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert resp.status_code == 201
    assert await _reported_count(client, admin, event_id) == p
    assert await _persisted_count(db_session, event_id) == p

    # Phase 1 - the failover window: K different students RSVP while the primary
    # is unreachable. Every write must fail; none may leak a phantom increment.
    k = 8
    in_flight = [
        await _register(client, f"failover-mid-{i}@example.com") for i in range(k)
    ]
    with patch.object(RsvpRepository, "create", new=_primary_unreachable):
        results = await asyncio.gather(
            *(client.post(f"/events/{event_id}/rsvp", headers=h) for h in in_flight),
            return_exceptions=True,
        )
    # Whether the app surfaces the dropped primary as a 5xx response or by
    # propagating, the one thing forbidden is a successful RSVP.
    accepted = [
        r for r in results if not isinstance(r, BaseException) and r.status_code == 201
    ]
    assert accepted == [], "no RSVP may commit while the primary is down"

    # The committed count is intact and the counter never advanced past it.
    assert await _reported_count(client, admin, event_id) == p
    assert await _persisted_count(db_session, event_id) == p
    pre_recovery = await RsvpService().reconcile_event(db_session, uuid.UUID(event_id))
    assert pre_recovery.redis_before == p
    assert pre_recovery.corrected is False

    # Phase 2 - standby promoted: the same K students retry and now succeed.
    for headers in in_flight:
        resp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert resp.status_code == 201

    total = p + k
    assert await _reported_count(client, admin, event_id) == total
    assert await _persisted_count(db_session, event_id) == total

    # Final invariant: counter and persisted rows agree - no drift introduced by
    # the failover, so reconciliation finds nothing to correct.
    post_recovery = await RsvpService().reconcile_event(db_session, uuid.UUID(event_id))
    assert post_recovery.db_count == total
    assert post_recovery.redis_before == total
    assert post_recovery.corrected is False
