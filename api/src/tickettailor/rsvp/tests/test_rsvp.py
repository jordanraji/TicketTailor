from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth_headers(
    client: AsyncClient,
    email: str,
    display_name: str = "Test User",
) -> tuple[dict[str, str], str]:
    password = "CorrectHorseBatteryStaple1!"
    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}, user_id


async def _create_club(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "UQ Computing Society",
) -> str:
    response = await client.post(
        "/clubs",
        json={
            "name": name,
            "description": "Technology events for students",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _create_event(
    client: AsyncClient,
    headers: dict[str, str],
    club_id: str,
    title: str = "Event Title",
    visibility: str = "public",
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
            "visibility": visibility,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _add_club_member(
    client: AsyncClient,
    admin_headers: dict[str, str],
    club_id: str,
    target_user_id: str,
) -> None:
    response = await client.post(
        f"/clubs/{club_id}/members",
        json={
            "user_id": target_user_id,
            "role": "committee_member",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201


async def test_rsvp_endpoints_require_authentication(
    client: AsyncClient,
) -> None:
    event_id = "00000000-0000-0000-0000-000000000000"

    post_resp = await client.post(f"/events/{event_id}/rsvp")
    assert post_resp.status_code == 401

    del_resp = await client.delete(f"/events/{event_id}/rsvp")
    assert del_resp.status_code == 401

    get_resp = await client.get(f"/events/{event_id}/rsvp")
    assert get_resp.status_code == 401


async def test_rsvp_public_event_flow(client: AsyncClient) -> None:
    admin_headers, _ = await _auth_headers(client, "rsvp-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Public RSVP Club")
    event_id = await _create_event(client, admin_headers, club_id, "Public Event")

    student_headers, _ = await _auth_headers(client, "rsvp-student@example.com")

    # 1. Initial status check (should be is_going=False, count=0)
    status_resp = await client.get(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json() == {"is_going": False, "attendee_count": 0}

    # 2. Place RSVP (returns 201 Created with attendee_count=1)
    rsvp_resp = await client.post(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert rsvp_resp.status_code == 201
    assert rsvp_resp.json() == {"attendee_count": 1}

    # 3. Status check after placing RSVP
    status_resp = await client.get(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json() == {"is_going": True, "attendee_count": 1}

    # 4. Attempt duplicate RSVP (raises 409 Conflict)
    duplicate_resp = await client.post(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert duplicate_resp.status_code == 409
    assert duplicate_resp.json()["title"] == "Already RSVP'd"

    # 5. Cancel RSVP (returns 200 OK with attendee_count=0)
    cancel_resp = await client.delete(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json() == {"attendee_count": 0}

    # 6. Status check after canceling RSVP
    status_resp = await client.get(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json() == {"is_going": False, "attendee_count": 0}

    # 7. Attempt duplicate cancellation (raises 404 Not Found)
    cancel_dup_resp = await client.delete(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert cancel_dup_resp.status_code == 404
    assert cancel_dup_resp.json()["title"] == "RSVP Not Found"


async def test_rsvp_club_only_event_privacy(client: AsyncClient) -> None:
    admin_headers, _ = await _auth_headers(client, "rsvp-club-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Club Only RSVP Club")
    event_id = await _create_event(
        client,
        admin_headers,
        club_id,
        "Private Event",
        visibility="club_only",
    )

    member_headers, member_id = await _auth_headers(client, "rsvp-member@example.com")
    outsider_headers, _ = await _auth_headers(client, "rsvp-outsider@example.com")

    # 1. Non-member is blocked from placing RSVP
    outsider_rsvp_resp = await client.post(
        f"/events/{event_id}/rsvp",
        headers=outsider_headers,
    )
    assert outsider_rsvp_resp.status_code == 403
    assert outsider_rsvp_resp.json()["title"] == "Forbidden"

    # 2. Non-member is blocked from querying status
    outsider_status_resp = await client.get(
        f"/events/{event_id}/rsvp",
        headers=outsider_headers,
    )
    assert outsider_status_resp.status_code == 403

    # 3. Add target user as a member of the club
    await _add_club_member(client, admin_headers, club_id, member_id)

    # 4. Now member can place RSVP successfully
    member_rsvp_resp = await client.post(
        f"/events/{event_id}/rsvp",
        headers=member_headers,
    )
    assert member_rsvp_resp.status_code == 201
    assert member_rsvp_resp.json() == {"attendee_count": 1}

    # 5. Member can query status successfully
    member_status_resp = await client.get(
        f"/events/{event_id}/rsvp",
        headers=member_headers,
    )
    assert member_status_resp.status_code == 200
    assert member_status_resp.json() == {"is_going": True, "attendee_count": 1}


async def test_rsvp_counter_agrees_with_persisted_rows(client: AsyncClient) -> None:
    """The Redis counter (ADR-0005) must agree with the persisted RSVP rows.

    Several distinct users RSVP and some cancel; the reported count must equal
    the number currently in the "going" state - the QA3 reconciliation property,
    here with no induced drift.
    """
    admin_headers, _ = await _auth_headers(client, "rsvp-count-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Counter Club")
    event_id = await _create_event(client, admin_headers, club_id, "Counter Event")

    # Five distinct students RSVP; the count must climb 1..5 deterministically.
    student_headers: list[dict[str, str]] = []
    for i in range(5):
        headers, _ = await _auth_headers(client, f"rsvp-count-{i}@example.com")
        student_headers.append(headers)
        resp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert resp.status_code == 201
        assert resp.json()["attendee_count"] == i + 1

    # One of those same students cancels; count drops to 4 and status agrees.
    cancel_resp = await client.delete(
        f"/events/{event_id}/rsvp", headers=student_headers[0]
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["attendee_count"] == 4

    status_resp = await client.get(f"/events/{event_id}/rsvp", headers=admin_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["attendee_count"] == 4


async def test_rsvp_count_seeds_from_db_on_cold_cache(
    client: AsyncClient,
    redis_url: str,
) -> None:
    """A cold counter key is seeded read-through from the DB count (ADR-0005).

    Simulates Redis having been flushed/restarted mid-life: after wiping the
    key, the next status read must recompute the correct count from PostgreSQL
    rather than reporting zero.
    """
    import redis.asyncio as aioredis

    admin_headers, _ = await _auth_headers(client, "rsvp-seed-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Seed Club")
    event_id = await _create_event(client, admin_headers, club_id, "Seed Event")

    for i in range(3):
        headers, _ = await _auth_headers(client, f"rsvp-seed-{i}@example.com")
        resp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert resp.status_code == 201

    # Wipe the live counter to simulate a Redis restart / eviction.
    raw = aioredis.from_url(redis_url, decode_responses=True)
    await raw.delete(f"rsvp:count:{event_id}")
    assert await raw.get(f"rsvp:count:{event_id}") is None
    await raw.aclose()

    # The next read must seed from the DB and report the true count, not zero.
    status_resp = await client.get(f"/events/{event_id}/rsvp", headers=admin_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["attendee_count"] == 3


async def test_rsvp_transactional_outbox_integration(
    client: AsyncClient,
    database_url: str,
) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from tickettailor.shared.models import OutboxEvent, OutboxEventType

    # 1. Setup a club and a public event
    admin_headers, _ = await _auth_headers(client, "rsvp-outbox-admin@example.com")
    club_id = await _create_club(client, admin_headers, "Outbox Club")
    event_id = await _create_event(client, admin_headers, club_id, "Outbox Event")

    student_headers, student_id = await _auth_headers(
        client, "rsvp-outbox-student@example.com"
    )

    # 2. Place RSVP
    rsvp_resp = await client.post(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert rsvp_resp.status_code == 201

    # 3. Check that the outbox event for rsvp_placed exists in the database
    engine = create_async_engine(database_url)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with sessionmaker() as session:
        stmt = select(OutboxEvent).where(
            OutboxEvent.event_type == OutboxEventType.rsvp_placed
        )
        result = await session.execute(stmt)
        events = result.scalars().all()

        # Verify the event details
        rsvp_placed_events = [
            ev for ev in events if ev.payload.get("user_id") == student_id
        ]
        assert len(rsvp_placed_events) == 1
        placed_event = rsvp_placed_events[0]
        assert placed_event.payload["event_id"] == event_id
        assert placed_event.payload["user_id"] == student_id
        assert "rsvp_id" in placed_event.payload

    # 4. Cancel RSVP
    cancel_resp = await client.delete(
        f"/events/{event_id}/rsvp",
        headers=student_headers,
    )
    assert cancel_resp.status_code == 200

    # 5. Check that the outbox event for rsvp_cancelled exists in the database
    async with sessionmaker() as session:
        stmt = select(OutboxEvent).where(
            OutboxEvent.event_type == OutboxEventType.rsvp_cancelled
        )
        result = await session.execute(stmt)
        events = result.scalars().all()

        # Verify the event details
        rsvp_cancelled_events = [
            ev for ev in events if ev.payload.get("user_id") == student_id
        ]
        assert len(rsvp_cancelled_events) == 1
        cancelled_event = rsvp_cancelled_events[0]
        assert cancelled_event.payload["event_id"] == event_id
        assert cancelled_event.payload["user_id"] == student_id
        assert "rsvp_id" in cancelled_event.payload

    await engine.dispose()
