"""QA4-authz / FR4 - OWASP A01 broken access control for event mutation.

``test_event_creation.py`` / ``test_event_crud.py`` already prove a zero-privilege
*outsider* (member of no club) is blocked. This file covers the sharper
cross-tenant case: a legitimate organiser of club A must not be able to create,
update, or delete events belonging to club B. Privileges in one club must never
leak into another (the multi-tenant isolation property A01 is about).

Every club member is an organiser by design (``MembershipRole`` is only
``committee_member`` / ``admin``, both of which ``can_manage_events`` allows), so
"non-organiser" reduces to "not a member of *that* club" - which is exactly what
these cross-club checks exercise from the attacker-has-real-privileges angle.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


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
        json={"name": name, "description": "Authz test club"},
        headers=headers,
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def _event_payload(club_id: str, title: str = "Owned Event") -> dict[str, Any]:
    return {
        "club_id": club_id,
        "title": title,
        "latitude": "-27.4975",
        "longitude": "153.0137",
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "is_free": True,
        "visibility": "public",
    }


async def _create_event(
    client: AsyncClient, headers: dict[str, str], club_id: str
) -> str:
    response = await client.post(
        "/events", json=_event_payload(club_id), headers=headers
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _two_clubs_attacker_and_victim_event(
    client: AsyncClient,
) -> tuple[dict[str, str], str, str]:
    """Set up an attacker who is admin of their own club A, plus a victim club B
    with an event. Returns (attacker_headers, club_b_id, event_in_b_id).

    Emails and club names are unique per call: the session DB is shared across
    tests (no truncation), and both are unique-constrained.
    """
    tag = uuid.uuid4().hex[:8]
    attacker = await _auth_headers(client, f"attacker-{tag}@example.com")
    await _create_club(client, attacker, f"Attacker Club {tag}")  # admin of A

    victim = await _auth_headers(client, f"victim-{tag}@example.com")
    club_b = await _create_club(client, victim, f"Victim Club {tag}")
    event_in_b = await _create_event(client, victim, club_b)
    return attacker, club_b, event_in_b


async def test_organiser_cannot_create_event_in_another_club(
    client: AsyncClient,
) -> None:
    attacker, club_b, _ = await _two_clubs_attacker_and_victim_event(client)

    response = await client.post(
        "/events", json=_event_payload(club_b, "Injected Event"), headers=attacker
    )

    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


async def test_organiser_cannot_update_another_clubs_event(
    client: AsyncClient,
) -> None:
    attacker, _, event_in_b = await _two_clubs_attacker_and_victim_event(client)

    response = await client.patch(
        f"/events/{event_in_b}",
        json={"title": "Hijacked Title"},
        headers=attacker,
    )

    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


async def test_organiser_cannot_delete_another_clubs_event(
    client: AsyncClient,
) -> None:
    attacker, _, event_in_b = await _two_clubs_attacker_and_victim_event(client)

    response = await client.delete(f"/events/{event_in_b}", headers=attacker)

    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"

    # The victim's event is untouched: it is still readable (it is public).
    reader = await _auth_headers(client, f"reader-{uuid.uuid4().hex[:8]}@example.com")
    still_there = await client.get(f"/events/{event_in_b}", headers=reader)
    assert still_there.status_code == 200
