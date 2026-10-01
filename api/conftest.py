"""Shared pytest fixtures for the TicketTailor API.

Integration tests run against a real PostgreSQL (PostGIS) database in a
throwaway container - the project convention (conventions.md) is "real
databases via testcontainers, don't mock the driver". The schema is built by
the project's own Alembic orchestrator (`tickettailor.shared.migrate`) so
tests exercise exactly the migrations that run in dev and prod.

This file lives at the API root (outside the `tickettailor` package) so it is
not type-checked by `mypy -p tickettailor` - the testcontainers/subprocess
glue here is deliberately untyped, while the tests themselves stay strict.
"""

import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

API_DIR = Path(__file__).resolve().parent

# Every data table, in one TRUNCATE so each test starts from an empty database.
# CASCADE handles the club_memberships -> clubs FK; the order is irrelevant.
# The Postgres container and schema are session-scoped, so tests would otherwise
# accumulate each other's rows (e.g. the events feed growing across tests).
_DATA_TABLES = (
    "auth.refresh_tokens",
    "calendar.calendar_tokens",
    "events.events",
    "organisers.club_memberships",
    "organisers.clubs",
    "rsvp.rsvps",
    "shared.outbox",
    "users.club_follows",
    "users.push_subscriptions",
    "users.users",
)
_TRUNCATE_SQL = f"TRUNCATE TABLE {', '.join(_DATA_TABLES)} RESTART IDENTITY CASCADE"


async def _truncate_all(engine: AsyncEngine) -> None:
    """Empty every data table so the test starts from a clean slate."""
    async with engine.begin() as conn:
        await conn.execute(text(_TRUNCATE_SQL))


# PostGIS image: the migration orchestrator runs every module's migrations,
# including `events`, whose geometry columns require the PostGIS extension.
POSTGRES_IMAGE = "postgis/postgis:16-3.4"

# Matches the image used by the local compose stack (docker-compose.yml).
REDIS_IMAGE = "redis:8-alpine"


def _async_url(container: PostgresContainer) -> str:
    return (
        f"postgresql+asyncpg://{container.username}:{container.password}"
        f"@{container.get_container_host_ip()}:"
        f"{container.get_exposed_port(5432)}/{container.dbname}"
    )


@pytest.fixture(scope="session")
def database_url() -> Generator[str, None, None]:
    """Start Postgres once per session and apply all migrations to it."""
    with PostgresContainer(POSTGRES_IMAGE) as container:
        url = _async_url(container)
        env = {**os.environ, "DATABASE_URL": url, "DATABASE_REPLICA_URL": url}
        # Run the real orchestrator in a subprocess: it uses asyncio.run()
        # internally, which cannot be nested inside the test event loop.
        result = subprocess.run(
            [sys.executable, "-m", "tickettailor.shared.migrate", "upgrade"],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Alembic migrations failed during test setup:\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        yield url


@pytest.fixture(scope="session")
def redis_url() -> Generator[str, None, None]:
    """Start Redis once per session for the RSVP atomic counter (ADR-0005)."""
    with RedisContainer(REDIS_IMAGE) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest_asyncio.fixture
async def db_session(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    """A bare DB session bound to the test container, for service-level tests
    of interfaces that aren't exposed over HTTP (e.g. the relay's fan-out
    queries). All data tables are truncated first so the test starts clean."""
    engine = create_async_engine(database_url)
    await _truncate_all(engine)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with sessionmaker() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await engine.dispose()


@pytest_asyncio.fixture
async def client(
    database_url: str, redis_url: str
) -> AsyncGenerator[AsyncClient, None]:
    """An httpx client wired to the app, with DB sessions bound to the container.

    The app's DB dependencies are overridden so we don't rely on the lifespan
    (ASGITransport does not run lifespan events) or on import-time settings.
    All data tables are truncated and the shared Redis client is flushed per
    test, so both stores start clean.
    """
    engine = create_async_engine(database_url)
    await _truncate_all(engine)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    from tickettailor.main import app
    from tickettailor.shared.app_services import (
        app_services,
        get_db_session,
        get_replica_db_session,
    )
    from tickettailor.shared.redis import RedisClient

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_replica_db_session] = _override_session

    # Point the process-wide Redis client at the test container and start clean.
    redis_client = RedisClient(redis_url=redis_url)
    await redis_client.client.flushdb()
    app_services.redis = redis_client

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        app_services.redis = None
        await redis_client.close()
        await engine.dispose()
