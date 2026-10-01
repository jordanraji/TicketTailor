"""QA3 reliability tests for the RSVP counter (ADR-0005, ADR-0008).

These exercise the *reliability* legs of the RSVP design under concurrency and
induced drift, complementing the single-threaded correctness cases in
``test_rsvp.py``:

* **QA3-idempotent** - a concurrently retried RSVP toggle never double-counts
  and never 500s; the loser of the unique-constraint race gets the same 409 as
  a serial duplicate.
* **QA3-replica / drift** - a burst of distinct concurrent RSVPs leaves the
  Redis counter, the reported count, and the persisted rows in agreement
  (the in-process analogue of cross-replica counter drift under load).
* **QA3-reconcile** - the reconciliation job (ADR-0005/0008) recomputes the
  count from PostgreSQL and corrects a drifted counter back to the truth.

Concurrency is driven with ``asyncio.gather`` against the ASGI app; each request
gets its own committed session via the ``client`` fixture override, so the
unique constraint and the atomic Redis counter are exercised for real against
the testcontainers Postgres + Redis.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.rsvp.service import RsvpService

pytestmark = pytest.mark.asyncio


async def _register(
    client: AsyncClient,
    email: str,
    display_name: str = "Test User",
) -> dict[str, str]:
    password = "password123"
    register_response = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


async def _create_club(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post(
        "/clubs",
        json={"name": name, "description": "Reliability fixtures"},
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _create_event(
    client: AsyncClient,
    headers: dict[str, str],
    club_id: str,
    title: str,
) -> str:
    response = await client.post(
        "/events",
        json={
            "club_id": club_id,
            "title": title,
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
    """The authoritative attendee count straight from the RSVP rows."""
    return await RsvpService().rsvp_repo.get_count_by_event(
        db_session, uuid.UUID(event_id)
    )


async def test_concurrent_distinct_rsvps_no_counter_drift(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A burst of distinct concurrent RSVPs keeps counter == rows (QA3-drift).

    Twenty different students RSVP to the same hot event simultaneously. Every
    request must succeed, and the live counter, the reported count, and the
    persisted rows must all converge on twenty - no lost increments under the
    atomic Redis ``INCR`` (ADR-0005).
    """
    admin_headers = await _register(client, "burst-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Burst Club")
    event_id = await _create_event(client, admin_headers, club_id, "Hot Event")

    n = 20
    student_headers = [
        await _register(client, f"burst-{i}@example.com") for i in range(n)
    ]

    responses = await asyncio.gather(
        *(
            client.post(f"/events/{event_id}/rsvp", headers=headers)
            for headers in student_headers
        )
    )
    assert [r.status_code for r in responses] == [201] * n

    # Reported live count (Redis) and the persisted rows must both equal N.
    status_resp = await client.get(f"/events/{event_id}/rsvp", headers=admin_headers)
    assert status_resp.json()["attendee_count"] == n
    assert await _persisted_count(db_session, event_id) == n

    # And the reconciliation job confirms zero drift.
    result = await RsvpService().reconcile_event(db_session, uuid.UUID(event_id))
    assert result.db_count == n
    assert result.redis_before == n
    assert result.corrected is False


async def test_concurrent_duplicate_rsvp_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A concurrently retried toggle yields exactly one RSVP (QA3-idempotent).

    The same student fires five identical RSVPs at once - a client retry storm.
    Exactly one must win (201); the rest must get the duplicate 409, never a
    500 from the unique-constraint race, and the count must settle at one with
    no double-count.
    """
    admin_headers = await _register(client, "dup-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Dup Club")
    event_id = await _create_event(client, admin_headers, club_id, "Dup Event")

    student_headers = await _register(client, "dup-student@example.com")

    responses = await asyncio.gather(
        *(
            client.post(f"/events/{event_id}/rsvp", headers=student_headers)
            for _ in range(5)
        )
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(201) == 1
    assert statuses.count(409) == 4
    assert set(statuses) == {201, 409}

    status_resp = await client.get(f"/events/{event_id}/rsvp", headers=student_headers)
    assert status_resp.json() == {"is_going": True, "attendee_count": 1}
    assert await _persisted_count(db_session, event_id) == 1


async def test_reconciliation_corrects_induced_drift(
    client: AsyncClient,
    db_session: AsyncSession,
    redis_url: str,
) -> None:
    """Reconciliation overwrites a drifted counter from the rows (QA3-reconcile).

    Three students RSVP, then we corrupt the Redis counter to a bogus value to
    simulate drift that the read-through seed (SET NX) cannot fix because the
    key still exists. ``reconcile_event`` must detect the mismatch, report the
    drifted value, and overwrite the counter with the persisted truth.
    """
    admin_headers = await _register(client, "reconcile-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Reconcile Club")
    event_id = await _create_event(client, admin_headers, club_id, "Reconcile Event")

    for i in range(3):
        headers = await _register(client, f"reconcile-{i}@example.com")
        resp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert resp.status_code == 201

    # Corrupt the live counter to simulate drift (e.g. a lost decrement).
    raw = aioredis.from_url(redis_url, decode_responses=True)
    await raw.set(f"rsvp:count:{event_id}", 99)

    result = await RsvpService().reconcile_event(db_session, uuid.UUID(event_id))
    assert result.redis_before == 99
    assert result.db_count == 3
    assert result.corrected is True

    # The counter now holds the truth, and reads reflect it without re-seeding.
    assert await raw.get(f"rsvp:count:{event_id}") == "3"
    await raw.aclose()

    status_resp = await client.get(f"/events/{event_id}/rsvp", headers=admin_headers)
    assert status_resp.json()["attendee_count"] == 3


async def test_reconcile_all_sweeps_every_live_counter(
    client: AsyncClient,
    db_session: AsyncSession,
    redis_url: str,
) -> None:
    """``reconcile_all`` finds and corrects drift across all counter keys.

    Two events drift independently; the on-demand sweep (ADR-0008) must scan
    the ``rsvp:count:*`` keyspace, reconcile both, and report a correction for
    each drifted event while leaving an in-sync event untouched.
    """
    admin_headers = await _register(client, "sweep-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Sweep Club")

    drifted_ids: list[str] = []
    for label in ("Sweep A", "Sweep B"):
        event_id = await _create_event(client, admin_headers, club_id, label)
        headers = await _register(client, f"sweep-{label.replace(' ', '')}@example.com")
        resp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert resp.status_code == 201
        drifted_ids.append(event_id)

    raw = aioredis.from_url(redis_url, decode_responses=True)
    for event_id in drifted_ids:
        await raw.set(f"rsvp:count:{event_id}", 42)
    await raw.aclose()

    results = await RsvpService().reconcile_all(db_session)
    by_id = {str(r.event_id): r for r in results}

    for event_id in drifted_ids:
        assert event_id in by_id, "reconcile_all must visit every live counter"
        assert by_id[event_id].corrected is True
        assert by_id[event_id].db_count == 1
        assert by_id[event_id].redis_before == 42
