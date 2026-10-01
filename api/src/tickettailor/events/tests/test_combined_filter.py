"""FR2 - map combined geo-radius + category filter (SD-05).

With a ``category`` the map returns only events that both fall inside the radius
and match the category; without it, category is ignored. Category matching never
overrides the radius - a matching event outside the radius is still excluded.

Coordinates are around UQ St Lucia (-27.4975, 153.0137).
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

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
        json={"name": name, "description": "Combined filter club"},
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
    category: str,
    latitude: str = QUERY_LAT,
    longitude: str = QUERY_LNG,
) -> str:
    payload: dict[str, Any] = {
        "club_id": club_id,
        "title": title,
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "is_free": True,
        "visibility": "public",
    }
    response = await client.post("/events", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


async def _search(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    radius_m: int,
    category: str | None = None,
) -> list[str]:
    params: dict[str, Any] = {
        "lat": QUERY_LAT,
        "lng": QUERY_LNG,
        "radius_m": radius_m,
    }
    if category is not None:
        params["category"] = category
    response = await client.get("/events", params=params, headers=headers)
    assert response.status_code == 200, response.text
    items = cast(list[dict[str, Any]], response.json()["items"])
    return [item["id"] for item in items]


async def test_category_narrows_results(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "cat-narrow@example.com")
    club_id = await _create_club(client, headers, "Narrow Club")
    social_id = await _create_event(
        client, headers, club_id, title="Trivia Night", category="social"
    )
    sports_id = await _create_event(
        client, headers, club_id, title="Touch Footy", category="sports"
    )

    social_only = await _search(client, headers, radius_m=5000, category="social")
    assert social_id in social_only
    assert sports_id not in social_only


async def test_no_category_returns_all_in_radius(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "cat-all@example.com")
    club_id = await _create_club(client, headers, "All Club")
    social_id = await _create_event(
        client, headers, club_id, title="Mixer", category="social"
    )
    sports_id = await _create_event(
        client, headers, club_id, title="Climbing", category="sports"
    )

    everything = await _search(client, headers, radius_m=5000)
    assert {social_id, sports_id} <= set(everything)


async def test_category_match_outside_radius_is_excluded(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "cat-radius@example.com")
    club_id = await _create_club(client, headers, "Radius Club")
    near_social = await _create_event(
        client, headers, club_id, title="Near social", category="social"
    )
    # Same category, but ~11 km away (0.1deg latitude) - outside the 2 km radius.
    far_social = await _create_event(
        client,
        headers,
        club_id,
        title="Far social",
        category="social",
        latitude="-27.5975",
    )

    results = await _search(client, headers, radius_m=2000, category="social")
    assert near_social in results
    assert far_social not in results
