import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _unique_email() -> str:
    return f"cal-{uuid.uuid4().hex}@example.com"


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
    name: str = "Calendar Club",
) -> str:
    response = await client.post(
        "/clubs",
        json={
            "name": name,
            "description": "Calendar test club",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _create_event(
    client: AsyncClient,
    headers: dict[str, str],
    club_id: str,
    title: str = "Calendar Event",
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


async def _rsvp_to_event(
    client: AsyncClient,
    headers: dict[str, str],
    event_id: str,
) -> None:
    response = await client.post(
        f"/events/{event_id}/rsvp",
        headers=headers,
    )
    assert response.status_code == 201


async def test_calendar_endpoints_require_authentication(
    client: AsyncClient,
) -> None:
    event_id = str(uuid.uuid4())

    # GET /calendar/token
    resp1 = await client.get("/calendar/token")
    assert resp1.status_code == 401

    # POST /calendar/token/rotate
    resp2 = await client.post("/calendar/token/rotate")
    assert resp2.status_code == 401

    # GET /events/{event_id}/calendar.ics
    resp3 = await client.get(f"/events/{event_id}/calendar.ics")
    assert resp3.status_code == 401


async def test_calendar_token_flow(client: AsyncClient) -> None:
    headers, _ = await _auth_headers(client, _unique_email())

    # 1. Fetch token for the first time (should generate it)
    resp = await client.get("/calendar/token", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "feed_url" in data
    first_token = data["token"]
    first_feed_url = data["feed_url"]
    assert first_token in first_feed_url

    # 2. Re-fetching should return the exact same token
    resp_re = await client.get("/calendar/token", headers=headers)
    assert resp_re.status_code == 200
    assert resp_re.json()["token"] == first_token

    # 3. Call the public feed URL (should be empty but 200 OK)
    feed_resp = await client.get(f"/calendar/feed/{first_token}")
    assert feed_resp.status_code == 200
    assert feed_resp.headers["content-type"] == "text/calendar; charset=utf-8"
    assert "BEGIN:VCALENDAR" in feed_resp.text
    assert "END:VCALENDAR" in feed_resp.text
    assert "BEGIN:VEVENT" not in feed_resp.text

    # 4. Rotate the token
    rotate_resp = await client.post("/calendar/token/rotate", headers=headers)
    assert rotate_resp.status_code == 200
    new_token = rotate_resp.json()["token"]
    assert new_token != first_token

    # 5. Old token should now return 404
    old_feed_resp = await client.get(f"/calendar/feed/{first_token}")
    assert old_feed_resp.status_code == 404

    # 6. New token should return 200
    new_feed_resp = await client.get(f"/calendar/feed/{new_token}")
    assert new_feed_resp.status_code == 200


async def test_single_event_ical_conformance(client: AsyncClient) -> None:
    admin_headers, _ = await _auth_headers(client, _unique_email())
    club_id = await _create_club(client, admin_headers, "Conform Club")
    event_id = await _create_event(client, admin_headers, club_id, "Conform Event")

    # 1. Download single event ics (authenticated)
    resp = await client.get(f"/events/{event_id}/calendar.ics", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/calendar; charset=utf-8"
    assert (
        resp.headers["content-disposition"]
        == f"attachment; filename=event-{event_id}.ics"
    )

    text = resp.text
    # 2. Check conformance to RFC 5545
    assert text.startswith("BEGIN:VCALENDAR")
    assert "VERSION:2.0" in text
    assert "PRODID:-//TicketTailor//Calendar Feed//EN" in text
    assert "BEGIN:VEVENT" in text
    assert f"UID:event-{event_id}@tickettailor.com" in text
    assert "DTSTAMP:" in text
    assert "DTSTART:" in text
    assert "DTEND:" in text
    assert "SUMMARY:Conform Event" in text
    assert "LOCATION:-27.4975\\,153.0137" in text
    assert "GEO:-27.4975;153.0137" in text
    assert "DESCRIPTION:TicketTailor Event: Conform Event" in text
    assert "END:VEVENT" in text
    assert text.endswith("END:VCALENDAR\r\n")

    # CRLF check
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")


async def test_user_feed_ical_integration(
    client: AsyncClient, database_url: str
) -> None:
    # 1. Setup Admin and Club
    admin_headers, _ = await _auth_headers(client, _unique_email())
    club_id = await _create_club(client, admin_headers, "Integration Club")

    # 2. Create Events
    public_event_id = await _create_event(
        client, admin_headers, club_id, "Public Event", visibility="public"
    )
    private_event_id = await _create_event(
        client,
        admin_headers,
        club_id,
        "Club Only Event",
        visibility="club_only",
    )

    # 3. Setup student, follow/join club and RSVP
    student_headers, student_id = await _auth_headers(client, _unique_email())
    # Add as club member so they can RSVP to club_only event
    await _add_club_member(client, admin_headers, club_id, student_id)

    # RSVP to both events
    await _rsvp_to_event(client, student_headers, public_event_id)
    await _rsvp_to_event(client, student_headers, private_event_id)

    # Get calendar token for student
    token_resp = await client.get("/calendar/token", headers=student_headers)
    token = token_resp.json()["token"]

    # 4. Fetch feed - both events should be present
    feed_resp = await client.get(f"/calendar/feed/{token}")
    assert feed_resp.status_code == 200
    text = feed_resp.text
    assert "SUMMARY:Public Event" in text
    assert "SUMMARY:Club Only Event" in text

    # 5. Remove student from club membership using DB session directly
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from tickettailor.organisers.service import ClubMembershipService

    engine = create_async_engine(database_url)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with sessionmaker() as db_sess:
        membership_service = ClubMembershipService()
        # Admin removes the student
        await membership_service.remove_member(
            db_sess,
            club_id=uuid.UUID(club_id),
            target_user_id=uuid.UUID(student_id),
            caller_user_id=uuid.UUID(student_id),  # target can remove self
        )
        await db_sess.commit()
    await engine.dispose()

    # 6. Fetch feed again - only public event should be present
    # (club-only event filtered out)
    feed_resp2 = await client.get(f"/calendar/feed/{token}")
    assert feed_resp2.status_code == 200
    text2 = feed_resp2.text
    assert "SUMMARY:Public Event" in text2
    assert "SUMMARY:Club Only Event" not in text2
