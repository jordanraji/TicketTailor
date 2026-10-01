"""FR1 - authentication flow integration tests (traceability: FR1, QA4-authz).

Covers signup -> login -> authenticated access -> 401 without credentials,
plus credential rejection and refresh-token rotation.
"""

import uuid

from httpx import AsyncClient

PASSWORD = "password123"


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    register = await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Test User"},
    )
    assert register.status_code == 201, register.text
    login = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    tokens: dict[str, str] = login.json()
    return tokens


async def test_register_returns_profile(client: AsyncClient) -> None:
    email = _unique_email()
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Ada"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == email
    assert body["display_name"] == "Ada"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


async def test_duplicate_registration_is_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    first = await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "A"},
    )
    assert first.status_code == 201
    second = await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "B"},
    )
    assert second.status_code == 400


async def test_login_returns_tokens(client: AsyncClient) -> None:
    tokens = await _register_and_login(client, _unique_email())
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"


async def test_login_with_wrong_password_is_401(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "A"},
    )
    response = await client.post(
        "/auth/login", json={"email": email, "password": "not-the-password"}
    )
    assert response.status_code == 401


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_returns_own_profile_with_token(client: AsyncClient) -> None:
    email = _unique_email()
    tokens = await _register_and_login(client, email)
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == email


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_revokes_old_token(client: AsyncClient) -> None:
    tokens = await _register_and_login(client, _unique_email())
    old_refresh = tokens["refresh_token"]

    rotated = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200, rotated.text
    new_tokens = rotated.json()
    assert new_tokens["refresh_token"] != old_refresh

    # The rotated-away token must no longer be accepted.
    reused = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    tokens = await _register_and_login(client, _unique_email())
    refresh_token = tokens["refresh_token"]

    logout = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    after = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert after.status_code == 401
