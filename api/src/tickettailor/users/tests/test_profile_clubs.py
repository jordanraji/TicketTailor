"""FR1 - user profile + club-affiliation integration tests.

Traceability: FR1 (profile read/write, club affiliation). Exercises the real
users routes through the shared auth dependency, so it also covers that
protected routes reject unauthenticated callers (QA4-authn).
"""

import uuid

from httpx import AsyncClient

PASSWORD = "password123"


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


async def _register(
    client: AsyncClient, email: str, display_name: str = "Test User"
) -> str:
    """Register a user and return their id."""
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": display_name},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Log in and return a Bearer auth header for the user."""
    login = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# --- profile read -----------------------------------------------------------


async def test_get_profile_returns_user(client: AsyncClient) -> None:
    email = _unique_email()
    user_id = await _register(client, email, display_name="Ada Lovelace")

    response = await client.get(f"/users/{user_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == user_id
    assert body["email"] == email
    assert body["display_name"] == "Ada Lovelace"
    assert body["role"] == "student"
    assert "password_hash" not in body


async def test_get_nonexistent_profile_is_404(client: AsyncClient) -> None:
    response = await client.get(f"/users/{uuid.uuid4()}")
    assert response.status_code == 404


# --- profile update ---------------------------------------------------------


async def test_update_profile_requires_auth(client: AsyncClient) -> None:
    response = await client.put("/users/profile", json={"display_name": "New Name"})
    assert response.status_code == 401


async def test_update_profile_changes_display_name(client: AsyncClient) -> None:
    email = _unique_email()
    user_id = await _register(client, email)
    headers = await _auth_headers(client, email)

    response = await client.put(
        "/users/profile", json={"display_name": "Renamed"}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Renamed"

    # The change is persisted, not just echoed.
    fetched = await client.get(f"/users/{user_id}")
    assert fetched.json()["display_name"] == "Renamed"


async def test_update_profile_changes_email(client: AsyncClient) -> None:
    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)
    new_email = _unique_email()

    response = await client.put(
        "/users/profile", json={"email": new_email}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["email"] == new_email


async def test_update_email_to_existing_is_rejected(client: AsyncClient) -> None:
    taken_email = _unique_email()
    await _register(client, taken_email)

    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)

    response = await client.put(
        "/users/profile", json={"email": taken_email}, headers=headers
    )

    assert response.status_code == 400


async def _create_club(client: AsyncClient, headers: dict[str, str]) -> str:
    """Create a club and return its ID."""
    name = f"Club-{uuid.uuid4().hex}"
    response = await client.post(
        "/clubs",
        json={"name": name, "description": "Test Club"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


# --- club follow / unfollow -------------------------------------------------


async def test_follow_club_requires_auth(client: AsyncClient) -> None:
    response = await client.post(f"/users/follow/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_follow_club_creates_affiliation(client: AsyncClient) -> None:
    email = _unique_email()
    user_id = await _register(client, email)
    headers = await _auth_headers(client, email)
    club_id = await _create_club(client, headers)

    response = await client.post(f"/users/follow/{club_id}", headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_id"] == user_id
    assert body["club_id"] == club_id


async def test_follow_same_club_twice_is_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)
    club_id = await _create_club(client, headers)

    first = await client.post(f"/users/follow/{club_id}", headers=headers)
    assert first.status_code == 201
    second = await client.post(f"/users/follow/{club_id}", headers=headers)
    assert second.status_code == 400


async def test_unfollow_club(client: AsyncClient) -> None:
    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)
    club_id = await _create_club(client, headers)

    await client.post(f"/users/follow/{club_id}", headers=headers)
    response = await client.delete(f"/users/follow/{club_id}", headers=headers)
    assert response.status_code == 204


async def test_unfollow_club_not_followed_is_404(client: AsyncClient) -> None:
    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)
    club_id = await _create_club(client, headers)

    response = await client.delete(f"/users/follow/{club_id}", headers=headers)
    assert response.status_code == 404


async def test_two_users_follow_same_club_independently(
    client: AsyncClient,
) -> None:
    email_a = _unique_email()
    await _register(client, email_a)
    headers_a = await _auth_headers(client, email_a)

    club_id = await _create_club(client, headers_a)

    email_b = _unique_email()
    await _register(client, email_b)
    headers_b = await _auth_headers(client, email_b)

    resp_a = await client.post(f"/users/follow/{club_id}", headers=headers_a)
    resp_b = await client.post(f"/users/follow/{club_id}", headers=headers_b)

    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


# --- push subscriptions -----------------------------------------------------


async def test_vapid_public_key_is_public(client: AsyncClient) -> None:
    response = await client.get("/users/push/vapid-public-key")
    assert response.status_code == 200
    assert "public_key" in response.json()


async def test_subscribe_push_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/users/push/subscriptions",
        json={"endpoint": "https://push.example/x", "p256dh": "k", "auth": "a"},
    )
    assert response.status_code == 401


async def test_subscribe_and_unsubscribe_push(client: AsyncClient) -> None:
    email = _unique_email()
    user_id = await _register(client, email)
    headers = await _auth_headers(client, email)
    endpoint = f"https://push.example/{uuid.uuid4().hex}"

    subscribe = await client.post(
        "/users/push/subscriptions",
        json={"endpoint": endpoint, "p256dh": "pub-key", "auth": "auth-secret"},
        headers=headers,
    )
    assert subscribe.status_code == 201, subscribe.text
    assert subscribe.json()["user_id"] == user_id
    assert subscribe.json()["endpoint"] == endpoint

    unsubscribe = await client.delete(
        "/users/push/subscriptions",
        params={"endpoint": endpoint},
        headers=headers,
    )
    assert unsubscribe.status_code == 204


async def test_resubscribe_same_endpoint_is_idempotent(
    client: AsyncClient,
) -> None:
    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)
    endpoint = f"https://push.example/{uuid.uuid4().hex}"

    first = await client.post(
        "/users/push/subscriptions",
        json={"endpoint": endpoint, "p256dh": "k1", "auth": "a1"},
        headers=headers,
    )
    second = await client.post(
        "/users/push/subscriptions",
        json={"endpoint": endpoint, "p256dh": "k2", "auth": "a2"},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    # Same subscription row reused (upsert on (user_id, endpoint)).
    assert first.json()["id"] == second.json()["id"]


async def test_unsubscribe_nonexistent_is_404(client: AsyncClient) -> None:
    email = _unique_email()
    await _register(client, email)
    headers = await _auth_headers(client, email)

    response = await client.delete(
        "/users/push/subscriptions",
        params={"endpoint": "https://push.example/never-subscribed"},
        headers=headers,
    )
    assert response.status_code == 404
