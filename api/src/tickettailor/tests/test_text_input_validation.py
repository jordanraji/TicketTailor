"""QA4-input regression - reject text PostgreSQL/asyncpg cannot store.

Schemathesis fuzzing found that a NUL (0x00) byte in a free-text field 500'd
(PostgreSQL text cannot hold NUL; a lone UTF-16 surrogate also fails to encode,
including when argon2 hashes a password). ``StrictTextModel`` now rejects both as
a 422 at the boundary. These pin the behaviour directly for the surfaced field
(register's display_name/password) and confirm it applies cross-module (clubs).

The bad inputs are sent as pre-serialised JSON bytes: ``json.dumps`` escapes a
lone surrogate to an ASCII ``\\udXXX`` sequence (valid on the wire, decoded back
to the surrogate server-side), whereas httpx's ``json=`` helper would fail to
UTF-8 encode it client-side - the same way the real fuzzer delivers it.
"""

import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

NUL = "bad\x00name"
LONE_SURROGATE = "bad\ud8e5name"  # high surrogate with no following low surrogate
_JSON = {"content-type": "application/json"}


def _email() -> str:
    return f"text-{uuid.uuid4().hex}@example.com"


def _body(payload: dict[str, Any]) -> bytes:
    # ensure_ascii=True (default) escapes NUL/surrogates to ASCII \uXXXX, so the
    # bytes are always encodable - the server decodes them back on json.loads.
    return json.dumps(payload).encode("ascii")


async def test_register_rejects_nul_in_display_name(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        content=_body(
            {"email": _email(), "password": "password123", "display_name": NUL}
        ),
        headers=_JSON,
    )
    assert resp.status_code == 422


async def test_register_rejects_lone_surrogate_in_display_name(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/auth/register",
        content=_body(
            {
                "email": _email(),
                "password": "password123",
                "display_name": LONE_SURROGATE,
            }
        ),
        headers=_JSON,
    )
    assert resp.status_code == 422


async def test_register_rejects_lone_surrogate_in_password(
    client: AsyncClient,
) -> None:
    # Would otherwise crash inside argon2 when it UTF-8 encodes the password.
    resp = await client.post(
        "/auth/register",
        content=_body(
            {
                "email": _email(),
                "password": "pass" + LONE_SURROGATE,
                "display_name": "Fine Name",
            }
        ),
        headers=_JSON,
    )
    assert resp.status_code == 422


async def test_valid_text_still_registers(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={
            "email": _email(),
            "password": "password123",
            "display_name": "Ada Lovelace",
        },
    )
    assert resp.status_code == 201


async def test_club_create_rejects_nul_name(client: AsyncClient) -> None:
    email = _email()
    register = await client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "Organiser"},
    )
    assert register.status_code == 201
    login = await client.post(
        "/auth/login", json={"email": email, "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", **_JSON}

    resp = await client.post(
        "/clubs",
        content=_body({"name": NUL, "description": "ok"}),
        headers=headers,
    )
    assert resp.status_code == 422


async def test_geo_search_rejects_nul_in_category_query_param(
    client: AsyncClient,
) -> None:
    # `category` is a query param, not a body field, so StrictTextModel does not
    # cover it; an AfterValidator rejects unstorable text before it reaches the
    # geo query and 500s. Surfaced by the QA4-input fuzzer on GET /events.
    resp = await client.get(
        "/events",
        params={
            "lat": "-83.45",
            "lng": "25.31",
            "radius_m": "258",
            "limit": "72",
            "category": NUL,
        },
    )
    assert resp.status_code == 422


async def test_geo_search_accepts_valid_category(client: AsyncClient) -> None:
    resp = await client.get(
        "/events",
        params={
            "lat": "-27.5",
            "lng": "153.0",
            "radius_m": "2000",
            "category": "music",
        },
    )
    assert resp.status_code == 200
