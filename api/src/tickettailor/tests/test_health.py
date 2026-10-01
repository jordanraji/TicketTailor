"""Behaviour of the operational probes (/healthz, /readyz).

These endpoints are excluded from the OpenAPI schema (include_in_schema=False),
so the schemathesis contract test does not exercise them - this is the only
place their behaviour is asserted.

- /healthz is a cheap, dependency-free liveness probe.
- /readyz gates traffic on the primary database being reachable. Redis is
  reported but NON-gating: the RSVP path degrades to the DB count when Redis is
  down (ADR-0005), so a Redis outage must not pull every task out of the ALB.

/readyz reads app_services.get_primary_db() directly (it checks the app's own
pool, not the request-scoped session the other tests override), so these tests
wire app_services explicitly and reset it afterwards.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tickettailor.main import app
from tickettailor.shared.app_services import app_services
from tickettailor.shared.database import PostgreSQLClient
from tickettailor.shared.redis import RedisClient

# An address that refuses connections immediately, to drive the not-ready path.
_UNREACHABLE_DB = "postgresql+asyncpg://nouser:nopass@127.0.0.1:1/nodb"


@pytest_asyncio.fixture
async def probe_client() -> AsyncIterator[AsyncClient]:
    """An httpx client over the app, disposing whatever the test wired onto the
    process-global app_services and resetting it to a clean state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    if app_services.primary_db is not None:
        await app_services.primary_db.engine.dispose()
        app_services.primary_db = None
    if app_services.redis is not None:
        await app_services.redis.close()
        app_services.redis = None


async def test_healthz_is_dependency_free(probe_client: AsyncClient) -> None:
    """Liveness returns 200 without touching any datastore."""
    resp = await probe_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_readyz_ready_when_dependencies_reachable(
    probe_client: AsyncClient, database_url: str, redis_url: str
) -> None:
    """With the primary DB and Redis reachable, readiness reports 200 / ready."""
    app_services.primary_db = PostgreSQLClient(database_url=database_url)
    app_services.redis = RedisClient(redis_url=redis_url)

    resp = await probe_client.get("/readyz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"


async def test_readyz_not_ready_when_database_unreachable(
    probe_client: AsyncClient, redis_url: str
) -> None:
    """An unreachable primary DB yields 503 so the ALB drains the task."""
    app_services.primary_db = PostgreSQLClient(database_url=_UNREACHABLE_DB)
    app_services.redis = RedisClient(redis_url=redis_url)

    resp = await probe_client.get("/readyz")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"].startswith("error")


async def test_readyz_ready_when_only_redis_down(
    probe_client: AsyncClient, database_url: str
) -> None:
    """Redis is non-gating (ADR-0005): a Redis outage alone stays ready (200)."""
    app_services.primary_db = PostgreSQLClient(database_url=database_url)
    app_services.redis = RedisClient(redis_url="redis://127.0.0.1:1/0")

    resp = await probe_client.get("/readyz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"].startswith("degraded")
