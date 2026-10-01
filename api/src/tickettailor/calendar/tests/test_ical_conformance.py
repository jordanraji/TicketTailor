"""QA2 / FR6 - iCal output conformance to RFC 5545.

Where ``test_calendar.py`` asserts substrings, this re-parses the served feed
with the ``icalendar`` RFC 5545 implementation and validates structure and
encoding rules a string match cannot catch:

* the feed parses at all, and carries the VCALENDAR-required VERSION (2.0) and
  PRODID (RFC 5545 s3.6);
* every VEVENT carries the required UID, DTSTAMP and DTSTART (s3.6.1);
* TEXT values containing the reserved characters ``, ; \\`` survive a
  serialise -> parse round-trip unchanged (escaping, s3.3.11) - the property a
  naive ``f"...{title}..."`` would silently break;
* content lines are folded to <=75 octets with CRLF endings (s3.1).

Driven through the HTTP feed endpoints so the conformance claim covers the exact
bytes served to Google/Outlook/Apple Calendar.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from httpx import AsyncClient
from icalendar import Calendar

pytestmark = pytest.mark.asyncio


def _parse(text: str) -> Any:
    """Re-parse served iCal with the RFC 5545 implementation (raises on junk)."""
    return Calendar.from_ical(text)


def _unique_email() -> str:
    return f"ical-{uuid.uuid4().hex}@example.com"


async def _auth_headers(client: AsyncClient, email: str) -> tuple[dict[str, str], str]:
    password = "password123"
    register = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Organiser"},
    )
    assert register.status_code == 201
    user_id = register.json()["id"]
    login = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user_id


async def _create_club(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/clubs",
        json={"name": f"Cal Club {uuid.uuid4().hex[:8]}", "description": "iCal club"},
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
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


async def _single_event_ics(client: AsyncClient, title: str) -> str:
    headers, _ = await _auth_headers(client, _unique_email())
    club_id = await _create_club(client, headers)
    event_id = await _create_event(client, headers, club_id, title)
    response = await client.get(f"/events/{event_id}/calendar.ics", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    return response.text


async def test_single_event_feed_parses_as_valid_rfc5545(client: AsyncClient) -> None:
    text = await _single_event_ics(client, "Conformance Concert")

    cal = _parse(text)
    # VCALENDAR-level required properties (RFC 5545 s3.6).
    assert str(cal.get("version")) == "2.0"
    assert cal.get("prodid") is not None

    vevents = cal.walk("VEVENT")
    assert len(vevents) == 1
    event = vevents[0]
    # VEVENT required properties (RFC 5545 s3.6.1).
    assert event.get("uid") is not None
    assert event.get("dtstamp") is not None
    assert event.get("dtstart") is not None
    assert str(event.get("summary")) == "Conformance Concert"


async def test_text_values_with_reserved_chars_round_trip(client: AsyncClient) -> None:
    # Comma, semicolon and backslash are the RFC 5545 TEXT escapes (s3.3.11);
    # a correct serialiser escapes them and a parser recovers them exactly.
    title = "Jazz, Wine; Cheese \\ Night"
    text = await _single_event_ics(client, title)

    # The raw bytes must carry the escaped form, not the literal reserved chars.
    assert "SUMMARY:Jazz\\, Wine\\; Cheese \\\\ Night" in text

    cal = _parse(text)
    event = cal.walk("VEVENT")[0]
    assert str(event.get("summary")) == title


async def test_content_lines_are_folded_to_75_octets(client: AsyncClient) -> None:
    # A title well past 75 chars forces line folding (RFC 5545 s3.1).
    long_title = "Mega " + "Festival " * 12  # ~113 chars
    text = await _single_event_ics(client, long_title.strip())

    # Parses despite the fold...
    cal = _parse(text)
    assert str(cal.walk("VEVENT")[0].get("summary")) == long_title.strip()

    # ...and every served line is CRLF-terminated and <=75 octets.
    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, f"unfolded line: {line!r}"


async def test_empty_feed_is_a_valid_empty_vcalendar(client: AsyncClient) -> None:
    headers, _ = await _auth_headers(client, _unique_email())
    token = (await client.get("/calendar/token", headers=headers)).json()["token"]

    response = await client.get(f"/calendar/feed/{token}")
    assert response.status_code == 200

    cal = _parse(response.text)
    assert str(cal.get("version")) == "2.0"
    assert cal.walk("VEVENT") == []


async def test_multi_event_feed_parses_with_unique_uids(client: AsyncClient) -> None:
    headers, _ = await _auth_headers(client, _unique_email())
    club_id = await _create_club(client, headers)
    first = await _create_event(client, headers, club_id, "First Event")
    second = await _create_event(client, headers, club_id, "Second Event")
    for event_id in (first, second):
        rsvp = await client.post(f"/events/{event_id}/rsvp", headers=headers)
        assert rsvp.status_code == 201

    token = (await client.get("/calendar/token", headers=headers)).json()["token"]
    response = await client.get(f"/calendar/feed/{token}")
    assert response.status_code == 200

    cal = _parse(response.text)
    vevents = cal.walk("VEVENT")
    assert len(vevents) == 2
    for event in vevents:
        assert event.get("uid") is not None
        assert event.get("dtstamp") is not None
        assert event.get("dtstart") is not None
    uids = {str(event.get("uid")) for event in vevents}
    assert len(uids) == 2  # each event's UID is distinct
