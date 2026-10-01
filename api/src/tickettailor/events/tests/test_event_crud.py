from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    password = "CorrectHorseBatteryStaple1!"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "Event Manager",
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
    assert isinstance(access_token, str)
    return {"Authorization": f"Bearer {access_token}"}


async def _create_club(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
) -> str:
    response = await client.post(
        "/clubs",
        json={
            "name": name,
            "description": "Events CRUD test club",
        },
        headers=headers,
    )
    assert response.status_code == 201
    club_id = response.json()["id"]
    assert isinstance(club_id, str)
    return club_id


def _event_payload(
    club_id: str,
    title: str = "Original Event",
    visibility: str = "public",
) -> dict[str, object]:
    return {
        "club_id": club_id,
        "title": title,
        "latitude": "-27.4975",
        "longitude": "153.0137",
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "is_free": True,
        "visibility": visibility,
    }


async def _create_event(
    client: AsyncClient,
    headers: dict[str, str],
    club_id: str,
    title: str = "Original Event",
    visibility: str = "public",
) -> dict[str, object]:
    response = await client.post(
        "/events",
        json=_event_payload(club_id, title=title, visibility=visibility),
        headers=headers,
    )
    assert response.status_code == 201
    event = response.json()
    assert isinstance(event, dict)
    return event


async def test_get_event_by_id_success(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-get@example.com")
    club_id = await _create_club(client, headers, "CRUD Get Club")
    event = await _create_event(client, headers, club_id, title="Readable Event")

    response = await client.get(f"/events/{event['id']}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event["id"]
    assert data["title"] == "Readable Event"
    assert data["latitude"] == "-27.498"
    assert data["longitude"] == "153.014"


async def test_get_event_not_found(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-not-found@example.com")

    response = await client.get(
        "/events/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["title"] == "Event Not Found"


async def test_club_only_event_is_hidden_from_non_member(
    client: AsyncClient,
) -> None:
    owner_headers = await _auth_headers(client, "crud-private-owner@example.com")
    club_id = await _create_club(client, owner_headers, "CRUD Private Club")
    event = await _create_event(
        client,
        owner_headers,
        club_id,
        title="Private Club Event",
        visibility="club_only",
    )

    outsider_headers = await _auth_headers(client, "crud-private-outsider@example.com")

    get_response = await client.get(f"/events/{event['id']}", headers=outsider_headers)
    assert get_response.status_code == 403

    list_response = await client.get("/events", headers=outsider_headers)
    assert list_response.status_code == 200
    listed_ids = {event["id"] for event in list_response.json()["items"]}
    assert event["id"] not in listed_ids


async def test_list_events_returns_visible_created_events(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-list@example.com")
    club_id = await _create_club(client, headers, "CRUD List Club")
    first = await _create_event(client, headers, club_id, title="List Event One")
    second = await _create_event(client, headers, club_id, title="List Event Two")

    response = await client.get("/events", headers=headers)

    assert response.status_code == 200
    ids = {event["id"] for event in response.json()["items"]}
    assert first["id"] in ids
    assert second["id"] in ids


async def test_list_events_uses_cursor_pagination(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-cursor@example.com")
    club_id = await _create_club(client, headers, "CRUD Cursor Club")
    first = await _create_event(client, headers, club_id, title="Cursor Event One")
    second = await _create_event(client, headers, club_id, title="Cursor Event Two")

    target_ids = {first["id"], second["id"]}
    seen_ids: set[str] = set()
    cursor: str | None = None

    # Page through with limit=1 (exercising the cursor) until the feed is
    # exhausted or both targets are seen. We must drain rather than stop after a
    # fixed number of pages: the events table is session-scoped and other tests
    # add rows, so the two targets can sort well past the first handful of pages.
    # The cap only guards against a runaway loop - it is far above the number of
    # events any single test run creates.
    for _ in range(5000):
        url = "/events?limit=1"
        if cursor is not None:
            url = f"{url}&cursor={cursor}"

        response = await client.get(url, headers=headers)

        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) <= 1

        if page["items"]:
            seen_ids.add(page["items"][0]["id"])

        cursor = page["next_cursor"]
        if target_ids.issubset(seen_ids) or cursor is None:
            break

    assert target_ids.issubset(seen_ids)


async def test_list_events_rejects_invalid_cursor(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-invalid-cursor@example.com")

    response = await client.get("/events?cursor=not-a-valid-cursor", headers=headers)

    assert response.status_code == 400
    assert response.json()["title"] == "Invalid Cursor"


async def test_update_event_success_by_event_manager(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-update@example.com")
    club_id = await _create_club(client, headers, "CRUD Update Club")
    event = await _create_event(client, headers, club_id)

    response = await client.patch(
        f"/events/{event['id']}",
        json={
            "title": "Updated Event",
            "latitude": "-27.5000",
            "longitude": "153.0200",
            "is_free": False,
            "price": "15.00",
            "visibility": "club_only",
            "image_s3_key": "events/updated.png",
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Event"
    assert data["latitude"] == "-27.5000"
    assert data["longitude"] == "153.0200"
    assert data["is_free"] is False
    assert data["price"] == "15.00"
    assert data["visibility"] == "club_only"
    assert data["image_s3_key"] == "events/updated.png"


async def test_update_event_forbidden_for_non_manager(client: AsyncClient) -> None:
    owner_headers = await _auth_headers(client, "crud-owner@example.com")
    club_id = await _create_club(client, owner_headers, "CRUD Forbidden Club")
    event = await _create_event(client, owner_headers, club_id)

    outsider_headers = await _auth_headers(client, "crud-outsider@example.com")

    response = await client.patch(
        f"/events/{event['id']}",
        json={"title": "Should Not Update"},
        headers=outsider_headers,
    )

    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


async def test_update_event_requires_coordinate_pair(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-coordinate@example.com")
    club_id = await _create_club(client, headers, "CRUD Coordinate Club")
    event = await _create_event(client, headers, club_id)

    response = await client.patch(
        f"/events/{event['id']}",
        json={"latitude": "-27.5000"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_delete_event_success_by_event_manager(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "crud-delete@example.com")
    club_id = await _create_club(client, headers, "CRUD Delete Club")
    event = await _create_event(client, headers, club_id)

    delete_response = await client.delete(f"/events/{event['id']}", headers=headers)

    assert delete_response.status_code == 204

    get_response = await client.get(f"/events/{event['id']}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_event_forbidden_for_non_manager(client: AsyncClient) -> None:
    owner_headers = await _auth_headers(client, "crud-delete-owner@example.com")
    club_id = await _create_club(client, owner_headers, "CRUD Delete Forbidden Club")
    event = await _create_event(client, owner_headers, club_id)

    outsider_headers = await _auth_headers(client, "crud-delete-outsider@example.com")

    response = await client.delete(f"/events/{event['id']}", headers=outsider_headers)

    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


async def test_update_event_rejects_inconsistent_pricing(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "crud-pricing@example.com")
    club_id = await _create_club(client, headers, "CRUD Pricing Club")
    event = await _create_event(client, headers, club_id)

    response = await client.patch(
        f"/events/{event['id']}",
        json={"is_free": False},
        headers=headers,
    )

    assert response.status_code == 422


async def test_create_event_writes_outbox_event(
    client: AsyncClient,
    database_url: str,
) -> None:
    from tickettailor.shared.models import OutboxEvent, OutboxEventType

    headers = await _auth_headers(client, "crud-outbox-create@example.com")
    club_id = await _create_club(client, headers, "CRUD Outbox Create Club")

    response = await client.post(
        "/events",
        json=_event_payload(club_id, title="Outbox Created Event"),
        headers=headers,
    )

    assert response.status_code == 201
    event_id = response.json()["id"]

    engine = create_async_engine(database_url)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with sessionmaker() as session:
        result = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == OutboxEventType.event_created
            )
        )
        outbox_events = result.scalars().all()

    await engine.dispose()

    matching_events = [
        event for event in outbox_events if event.payload.get("event_id") == event_id
    ]
    assert len(matching_events) == 1
    assert str(matching_events[0].aggregate_id) == event_id
    assert matching_events[0].payload["club_id"] == club_id


async def test_update_event_writes_outbox_event(
    client: AsyncClient,
    database_url: str,
) -> None:
    from tickettailor.shared.models import OutboxEvent, OutboxEventType

    headers = await _auth_headers(client, "crud-outbox-update@example.com")
    club_id = await _create_club(client, headers, "CRUD Outbox Update Club")
    event = await _create_event(client, headers, club_id)

    response = await client.patch(
        f"/events/{event['id']}",
        json={"title": "Outbox Updated Event"},
        headers=headers,
    )

    assert response.status_code == 200

    engine = create_async_engine(database_url)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with sessionmaker() as session:
        result = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == OutboxEventType.event_updated
            )
        )
        outbox_events = result.scalars().all()

    await engine.dispose()

    matching_events = [
        outbox_event
        for outbox_event in outbox_events
        if outbox_event.payload.get("event_id") == event["id"]
    ]
    assert len(matching_events) == 1
    assert str(matching_events[0].aggregate_id) == event["id"]
    assert matching_events[0].payload["club_id"] == club_id
