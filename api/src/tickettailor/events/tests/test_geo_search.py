"""FR2 - map geo-radius browse (SD-05).

A query within R metres of a point returns events inside the radius and excludes
those outside it; results are ordered nearest-first with a ``distance_m``; the
radius is clamped to 50 km; the public map shows public events only; and an
incomplete geo filter is rejected. Runs against the real PostGIS container so
``ST_DWithin`` / ``ST_Distance`` are exercised for real.

Coordinates are around UQ St Lucia (-27.4975, 153.0137); 0.01deg of latitude is
~1.11 km, so offsets give predictable distances.
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient

from tickettailor.events.cache import EventGeoCache

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
        json={"name": name, "description": "Geo test club"},
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
    latitude: str,
    longitude: str,
    category: str | None = None,
    visibility: str = "public",
) -> str:
    payload: dict[str, Any] = {
        "club_id": club_id,
        "title": title,
        "latitude": latitude,
        "longitude": longitude,
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "is_free": True,
        "visibility": visibility,
    }
    if category is not None:
        payload["category"] = category
    response = await client.post("/events", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


async def _search(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    lat: str = QUERY_LAT,
    lng: str = QUERY_LNG,
    radius_m: int,
    category: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"lat": lat, "lng": lng, "radius_m": radius_m}
    if category is not None:
        params["category"] = category
    response = await client.get("/events", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return cast(list[dict[str, Any]], response.json()["items"])


async def test_event_within_radius_is_returned_with_distance(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "geo-within@example.com")
    club_id = await _create_club(client, headers, "Within Club")
    event_id = await _create_event(
        client,
        headers,
        club_id,
        title="At the point",
        latitude=QUERY_LAT,
        longitude=QUERY_LNG,
    )

    items = await _search(client, headers, radius_m=2000)

    ids = [item["id"] for item in items]
    assert event_id in ids
    match = next(item for item in items if item["id"] == event_id)
    assert match["distance_m"] is not None
    assert match["distance_m"] < 50  # essentially at the query point


async def test_event_outside_radius_is_excluded(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "geo-outside@example.com")
    club_id = await _create_club(client, headers, "Outside Club")
    # ~11 km south of the query point (0.1deg latitude), well outside a 2 km radius.
    far_id = await _create_event(
        client,
        headers,
        club_id,
        title="Eleven km away",
        latitude="-27.5975",
        longitude=QUERY_LNG,
    )

    items = await _search(client, headers, radius_m=2000)

    assert far_id not in [item["id"] for item in items]


async def test_results_ordered_nearest_first(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "geo-order@example.com")
    club_id = await _create_club(client, headers, "Order Club")
    near_id = await _create_event(
        client,
        headers,
        club_id,
        title="Near",
        latitude=QUERY_LAT,
        longitude=QUERY_LNG,
    )
    # ~5.5 km south (0.05deg latitude).
    mid_id = await _create_event(
        client,
        headers,
        club_id,
        title="Mid",
        latitude="-27.5475",
        longitude=QUERY_LNG,
    )

    items = await _search(client, headers, radius_m=20000)

    ordered_ids = [item["id"] for item in items if item["id"] in {near_id, mid_id}]
    assert ordered_ids == [near_id, mid_id]
    distances = [
        item["distance_m"] for item in items if item["id"] in {near_id, mid_id}
    ]
    assert distances == sorted(distances)


async def test_radius_is_clamped_to_50km(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "geo-clamp@example.com")
    club_id = await _create_club(client, headers, "Clamp Club")
    in_range_id = await _create_event(
        client,
        headers,
        club_id,
        title="Five km",
        latitude="-27.5475",  # ~5.5 km
        longitude=QUERY_LNG,
    )
    # ~60 km south (0.54deg latitude) - beyond the 50 km clamp ceiling.
    beyond_clamp_id = await _create_event(
        client,
        headers,
        club_id,
        title="Sixty km",
        latitude="-28.0375",
        longitude=QUERY_LNG,
    )

    # Ask for 100 km; the handler clamps to 50 km, so the 60 km event is excluded.
    items = await _search(client, headers, radius_m=100_000)

    ids = [item["id"] for item in items]
    assert in_range_id in ids
    assert beyond_clamp_id not in ids


async def test_club_only_events_are_not_on_the_public_map(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "geo-private@example.com")
    club_id = await _create_club(client, headers, "Private Club")
    private_id = await _create_event(
        client,
        headers,
        club_id,
        title="Members only",
        latitude=QUERY_LAT,
        longitude=QUERY_LNG,
        visibility="club_only",
    )

    items = await _search(client, headers, radius_m=2000)

    assert private_id not in [item["id"] for item in items]


async def test_incomplete_geo_filter_is_rejected(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "geo-incomplete@example.com")

    # lat without lng/radius_m is an incomplete filter.
    response = await client.get("/events", params={"lat": QUERY_LAT}, headers=headers)
    assert response.status_code == 400
    assert response.json()["title"] == "Incomplete Geo Filter"


async def test_geo_search_is_cached(client: AsyncClient, redis_url: str) -> None:
    """Verify that geo-search results are cached in Redis.

    Asserts that a subsequent search is served from Redis by verifying
    distance modification directly on the cached payload in Redis.
    """
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    cache = EventGeoCache(redis_client)

    cache_key = cache.build_key(
        latitude=Decimal(QUERY_LAT),
        longitude=Decimal(QUERY_LNG),
        radius_m=2000.0,
        limit=100,
        category=None,
    )
    await redis_client.delete(cache_key)

    headers = await _auth_headers(client, "geo-cache@example.com")
    club_id = await _create_club(client, headers, "Cache Club")
    event_id = await _create_event(
        client,
        headers,
        club_id,
        title="Cache Test Event",
        latitude=QUERY_LAT,
        longitude=QUERY_LNG,
    )

    items_first = await _search(client, headers, radius_m=2000)
    assert event_id in [item["id"] for item in items_first]

    raw_cached = await redis_client.get(cache_key)
    assert raw_cached is not None
    cached_payload = json.loads(raw_cached)

    for item in cached_payload:
        if item[0] == event_id:
            item[1] = 9999.9

    await redis_client.set(cache_key, json.dumps(cached_payload), ex=30)

    items_second = await _search(client, headers, radius_m=2000)
    match = next(item for item in items_second if item["id"] == event_id)
    assert match["distance_m"] == 9999.9

    await redis_client.aclose()


async def test_geo_search_cache_hit_excludes_private_events(
    client: AsyncClient, redis_url: str
) -> None:
    """Verify that a cached event is excluded from search results if its

    visibility is changed to club_only during the cache TTL window.
    """
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    cache = EventGeoCache(redis_client)

    cache_key = cache.build_key(
        latitude=Decimal(QUERY_LAT),
        longitude=Decimal(QUERY_LNG),
        radius_m=2000.0,
        limit=100,
        category=None,
    )
    await redis_client.delete(cache_key)

    headers = await _auth_headers(client, "geo-leak@example.com")
    club_id = await _create_club(client, headers, "Leak Club")
    event_id = await _create_event(
        client,
        headers,
        club_id,
        title="Cache Leak Test Event",
        latitude=QUERY_LAT,
        longitude=QUERY_LNG,
        visibility="public",
    )

    items_first = await _search(client, headers, radius_m=2000)
    assert event_id in [item["id"] for item in items_first]

    assert await redis_client.get(cache_key) is not None

    patch_resp = await client.patch(
        f"/events/{event_id}",
        json={"visibility": "club_only"},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    items_second = await _search(client, headers, radius_m=2000)
    assert event_id not in [item["id"] for item in items_second]

    await redis_client.aclose()
