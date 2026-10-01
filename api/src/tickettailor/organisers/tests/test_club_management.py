import uuid

from httpx import AsyncClient

PASSWORD = "password123"


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


async def _register_and_auth(client: AsyncClient, email: str) -> dict[str, str]:
    """Register a user, log in, and return headers with Bearer token."""
    await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Test User"},
    )
    login_resp = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Club Creation tests ----------------------------------------------------


async def test_create_club_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/clubs",
        json={"name": "Science Club", "description": "Physics and Chemistry"},
    )
    assert response.status_code == 401


async def test_create_club_success(client: AsyncClient) -> None:
    email = _unique_email()
    headers = await _register_and_auth(client, email)

    club_name = f"Club-{uuid.uuid4().hex}"
    response = await client.post(
        "/clubs",
        json={"name": club_name, "description": "Fun science activities"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == club_name
    assert body["description"] == "Fun science activities"
    assert "id" in body


async def test_create_club_duplicate_name_is_rejected(
    client: AsyncClient,
) -> None:
    email = _unique_email()
    headers = await _register_and_auth(client, email)
    club_name = f"Club-{uuid.uuid4().hex}"

    # First creation
    first = await client.post(
        "/clubs",
        json={"name": club_name, "description": "First"},
        headers=headers,
    )
    assert first.status_code == 201

    # Second creation with the same name
    second = await client.post(
        "/clubs",
        json={"name": club_name, "description": "Second"},
        headers=headers,
    )
    assert second.status_code == 400
    assert second.json()["title"] == "Club Already Exists"


# --- Club Retrieval tests ---------------------------------------------------


async def test_get_club_success(client: AsyncClient) -> None:
    email = _unique_email()
    headers = await _register_and_auth(client, email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post(
        "/clubs",
        json={"name": club_name, "description": "Retrieval Test"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    # Retrieve club details publicly (no auth header needed)
    response = await client.get(f"/clubs/{club_id}")
    assert response.status_code == 200
    assert response.json()["name"] == club_name
    assert response.json()["description"] == "Retrieval Test"


async def test_get_club_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/clubs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["title"] == "Club Not Found"


# --- Club Update tests ------------------------------------------------------


async def test_update_club_requires_auth(client: AsyncClient) -> None:
    email = _unique_email()
    headers = await _register_and_auth(client, email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post("/clubs", json={"name": club_name}, headers=headers)
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    response = await client.put(
        f"/clubs/{club_id}", json={"description": "Updated description"}
    )
    assert response.status_code == 401


async def test_update_club_success_by_admin(client: AsyncClient) -> None:
    email = _unique_email()
    headers = await _register_and_auth(client, email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post("/clubs", json={"name": club_name}, headers=headers)
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    response = await client.put(
        f"/clubs/{club_id}",
        json={"description": "Updated by admin"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated by admin"


async def test_update_club_forbidden_by_non_admin(client: AsyncClient) -> None:
    # Creator (Admin)
    admin_email = _unique_email()
    admin_headers = await _register_and_auth(client, admin_email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post(
        "/clubs", json={"name": club_name}, headers=admin_headers
    )
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    # Other student (Non-Admin)
    student_email = _unique_email()
    student_headers = await _register_and_auth(client, student_email)

    response = await client.put(
        f"/clubs/{club_id}",
        json={"description": "Intruder change"},
        headers=student_headers,
    )
    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


# --- Club Membership Addition tests -----------------------------------------


async def test_add_member_success(client: AsyncClient) -> None:
    # Admin registers and creates club
    admin_email = _unique_email()
    admin_headers = await _register_and_auth(client, admin_email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post(
        "/clubs", json={"name": club_name}, headers=admin_headers
    )
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    # Target user registers
    target_email = _unique_email()
    target_resp = await client.post(
        "/auth/register",
        json={
            "email": target_email,
            "password": PASSWORD,
            "display_name": "Target User",
        },
    )
    assert target_resp.status_code == 201
    target_id = target_resp.json()["id"]

    # Admin adds target user as committee member
    response = await client.post(
        f"/clubs/{club_id}/members",
        json={"user_id": target_id, "role": "committee_member"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == target_id
    assert body["club_id"] == club_id
    assert body["role"] == "committee_member"


async def test_add_member_duplicate_is_rejected(client: AsyncClient) -> None:
    # Admin registers and creates club
    admin_email = _unique_email()
    admin_headers = await _register_and_auth(client, admin_email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post(
        "/clubs", json={"name": club_name}, headers=admin_headers
    )
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    # Try to add the admin again (who is already registered as admin during creation)
    # Admin ID can be fetched from /auth/me
    me_resp = await client.get("/auth/me", headers=admin_headers)
    assert me_resp.status_code == 200
    admin_id = me_resp.json()["id"]

    response = await client.post(
        f"/clubs/{club_id}/members",
        json={"user_id": admin_id, "role": "committee_member"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["title"] == "Already Club Member"


async def test_add_member_requires_admin_role(client: AsyncClient) -> None:
    # Admin registers and creates club
    admin_email = _unique_email()
    admin_headers = await _register_and_auth(client, admin_email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post(
        "/clubs", json={"name": club_name}, headers=admin_headers
    )
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    # Student registers (not member)
    student_email = _unique_email()
    student_headers = await _register_and_auth(client, student_email)

    # Intruder registers
    intruder_email = _unique_email()
    intruder_resp = await client.post(
        "/auth/register",
        json={
            "email": intruder_email,
            "password": PASSWORD,
            "display_name": "Intruder",
        },
    )
    assert intruder_resp.status_code == 201
    intruder_id = intruder_resp.json()["id"]

    # Non-admin tries to add member
    response = await client.post(
        f"/clubs/{club_id}/members",
        json={"user_id": intruder_id, "role": "committee_member"},
        headers=student_headers,
    )
    assert response.status_code == 403


# --- Club listing tests -----------------------------------------------------


async def test_list_clubs_includes_created_club(client: AsyncClient) -> None:
    email = _unique_email()
    headers = await _register_and_auth(client, email)
    club_name = f"Club-{uuid.uuid4().hex}"

    create_resp = await client.post("/clubs", json={"name": club_name}, headers=headers)
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    # Listing is public (no auth header).
    response = await client.get("/clubs")
    assert response.status_code == 200
    ids = [club["id"] for club in response.json()]
    assert club_id in ids


async def test_my_clubs_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/clubs/my-clubs")
    assert response.status_code == 401


async def test_my_clubs_returns_only_the_users_clubs(client: AsyncClient) -> None:
    # Creator is auto-enrolled as admin of their club.
    owner_headers = await _register_and_auth(client, _unique_email())
    owned_name = f"Club-{uuid.uuid4().hex}"
    owned = await client.post(
        "/clubs", json={"name": owned_name}, headers=owner_headers
    )
    assert owned.status_code == 201
    owned_id = owned.json()["id"]

    # A different user creates their own club; it must not leak into owner's list.
    other_headers = await _register_and_auth(client, _unique_email())
    other = await client.post(
        "/clubs", json={"name": f"Club-{uuid.uuid4().hex}"}, headers=other_headers
    )
    assert other.status_code == 201
    other_id = other.json()["id"]

    response = await client.get("/clubs/my-clubs", headers=owner_headers)
    assert response.status_code == 200
    ids = [club["id"] for club in response.json()]
    assert ids == [owned_id]
    assert other_id not in ids


async def test_my_clubs_with_membership_returns_role(client: AsyncClient) -> None:
    headers = await _register_and_auth(client, _unique_email())
    club_name = f"Club-{uuid.uuid4().hex}"
    create_resp = await client.post("/clubs", json={"name": club_name}, headers=headers)
    assert create_resp.status_code == 201
    club_id = create_resp.json()["id"]

    response = await client.get("/clubs/my-clubs/with-membership", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == club_id
    # Creator is the admin of their own club.
    assert body[0]["user_role"] == "admin"
