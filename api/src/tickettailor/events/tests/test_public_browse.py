"""Public browse: anonymous callers can discover public events (list, map, and
detail) but never club-only events.

GET /events (list + geo) and GET /events/{id} authenticate optionally
(``optional_current_user_id``): a signed-in caller also sees their club-only
events, an anonymous caller sees only public ones, and writes/RSVP stay gated.
The real gate is the per-event visibility check in ``EventService``; these tests
pin that anonymous callers cannot see or read a club-only event (OWASP A01,
ADR-0009).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

QUERY_LAT = "-27.4975"
QUERY_LNG = "153.0137"


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    password = "password123"
    register = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Organiser"},
    )
    assert register.status_code == 201
    login = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _create_club(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post(
        "/clubs",
        json={"name": name, "description": "Public-browse fixtures"},
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _create_event(
    client: AsyncClient,
    headers: dict[str, str],
    club_id: str,
    *,
    title: str,
    visibility: str,
) -> str:
    response = await client.post(
        "/events",
        json={
            "club_id": club_id,
            "title": title,
            "latitude": QUERY_LAT,
            "longitude": QUERY_LNG,
            "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "is_free": True,
            "visibility": visibility,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


async def test_anonymous_list_shows_public_hides_club_only(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "pb-list@example.com")
    club_id = await _create_club(client, headers, "Public Browse Club")
    public_id = await _create_event(
        client, headers, club_id, title="Public Party", visibility="public"
    )
    private_id = await _create_event(
        client, headers, club_id, title="Members Only", visibility="club_only"
    )

    # No Authorization header => anonymous caller.
    resp = await client.get("/events")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert public_id in ids
    assert private_id not in ids


async def test_anonymous_geo_shows_public_only(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "pb-geo@example.com")
    club_id = await _create_club(client, headers, "Geo Club")
    public_id = await _create_event(
        client, headers, club_id, title="Public Geo", visibility="public"
    )
    private_id = await _create_event(
        client, headers, club_id, title="Private Geo", visibility="club_only"
    )

    resp = await client.get(f"/events?lat={QUERY_LAT}&lng={QUERY_LNG}&radius_m=2000")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert public_id in ids
    assert private_id not in ids


async def test_anonymous_can_read_public_detail(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "pb-detail@example.com")
    club_id = await _create_club(client, headers, "Detail Club")
    public_id = await _create_event(
        client, headers, club_id, title="Readable", visibility="public"
    )

    resp = await client.get(f"/events/{public_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == public_id


async def test_anonymous_cannot_read_club_only_detail(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "pb-hidden@example.com")
    club_id = await _create_club(client, headers, "Hidden Club")
    private_id = await _create_event(
        client, headers, club_id, title="Hidden", visibility="club_only"
    )

    resp = await client.get(f"/events/{private_id}")
    assert resp.status_code == 403


async def test_member_sees_own_club_only_in_list(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "pb-member@example.com")
    club_id = await _create_club(client, headers, "Member Club")
    private_id = await _create_event(
        client, headers, club_id, title="Member Event", visibility="club_only"
    )

    # The club creator is an organiser (and member), so they see the club-only
    # event when authenticated - the same endpoint that hides it from anonymous.
    resp = await client.get("/events", headers=headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert private_id in ids


async def test_anonymous_missing_event_is_404_not_401(client: AsyncClient) -> None:
    # A bad id from an anonymous caller is a clean 404, not an auth challenge.
    resp = await client.get(f"/events/{uuid.uuid4()}")
    assert resp.status_code == 404
