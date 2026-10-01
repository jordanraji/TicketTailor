from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth_headers(
    client: AsyncClient,
    email: str = "event-organiser@example.com",
) -> dict[str, str]:
    password = "CorrectHorseBatteryStaple1!"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Event Organiser",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


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
    club_id = response.json()["id"]
    assert isinstance(club_id, str)
    return club_id


def _event_payload(club_id: str) -> dict[str, object]:
    return {
        "club_id": club_id,
        "title": "Semester Networking Night",
        "latitude": "-27.4975",
        "longitude": "153.0137",
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "is_free": False,
        "price": "12.50",
        "visibility": "club_only",
        "transition_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "image_s3_key": "events/networking-night.png",
    }


async def test_create_event_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/events",
        json={
            "club_id": "00000000-0000-0000-0000-000000000000",
            "title": "Unauthenticated Event",
            "latitude": "-27.4975",
            "longitude": "153.0137",
            "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "is_free": True,
            "visibility": "public",
        },
    )

    assert response.status_code == 401


async def test_create_event_success_by_club_admin(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    club_id = await _create_club(client, headers)

    response = await client.post(
        "/events",
        json=_event_payload(club_id),
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["club_id"] == club_id
    assert data["title"] == "Semester Networking Night"
    assert data["created_by"] is not None
    assert data["latitude"] == "-27.4975"
    assert data["longitude"] == "153.0137"
    assert data["is_free"] is False
    assert data["price"] == "12.50"
    assert data["visibility"] == "club_only"
    assert data["image_s3_key"] == "events/networking-night.png"


async def test_create_event_forbidden_for_non_member(client: AsyncClient) -> None:
    organiser_headers = await _auth_headers(client, "organiser@example.com")
    club_id = await _create_club(client, organiser_headers, "Forbidden Test Club")

    outsider_headers = await _auth_headers(client, "outsider@example.com")

    response = await client.post(
        "/events",
        json=_event_payload(club_id),
        headers=outsider_headers,
    )

    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


async def test_free_event_rejects_price(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "free-event-organiser@example.com")
    club_id = await _create_club(client, headers, "Free Event Validation Club")

    payload = _event_payload(club_id)
    payload["is_free"] = True
    payload["price"] = "5.00"

    response = await client.post(
        "/events",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422
