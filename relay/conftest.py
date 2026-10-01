"""Shared pytest fixtures for the relay.

Like the API tests (conventions.md: "real databases via testcontainers, don't
mock the driver"), the relay's integration tests run against a real PostGIS
container whose schema is built by the API's own Alembic orchestrator
(`tickettailor.shared.migrate`) - so the relay exercises exactly the `events`
and `shared.outbox` tables that ship in dev and prod.

This file lives at the relay root (outside the `relay` package) so it is not
type-checked by `mypy -p relay`; the testcontainers/subprocess glue is
deliberately untyped while the tests themselves stay strict.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from tickettailor.events.models import Event, EventVisibility

# PostGIS image: the events table has a geometry column requiring PostGIS.
POSTGRES_IMAGE = "postgis/postgis:16-3.4"


def _async_url(container: PostgresContainer) -> str:
    return (
        f"postgresql+asyncpg://{container.username}:{container.password}"
        f"@{container.get_container_host_ip()}:"
        f"{container.get_exposed_port(5432)}/{container.dbname}"
    )


@pytest.fixture(scope="session")
def database_url() -> Generator[str, None, None]:
    """Start Postgres once per session and apply all API migrations to it."""
    with PostgresContainer(POSTGRES_IMAGE) as container:
        url = _async_url(container)
        env = {**os.environ, "DATABASE_URL": url, "DATABASE_REPLICA_URL": url}
        # The orchestrator calls asyncio.run() internally, so it must run in a
        # subprocess rather than nested inside the test event loop. It chdir's
        # to the API dir itself, so cwd here doesn't matter.
        result = subprocess.run(
            [sys.executable, "-m", "tickettailor.shared.migrate", "upgrade"],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Alembic migrations failed during relay test setup:\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        yield url


@pytest_asyncio.fixture
async def sessionmaker(
    database_url: str,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """A sessionmaker bound to the container, with events/outbox truncated so
    each test starts from a clean slate."""
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE events.events, shared.outbox, rsvp.rsvps, "
                "users.club_follows, users.push_subscriptions, users.users "
                "RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
def make_event(
    sessionmaker: async_sessionmaker[AsyncSession],
):
    """Factory inserting an Event row directly (relay tests work below the API).

    ``transition_offset`` is relative to now: negative = already due, positive =
    in the future, ``None`` = no scheduled transition.
    """

    async def _make_event(
        *,
        visibility: EventVisibility = EventVisibility.club_only,
        transition_offset: timedelta | None = timedelta(minutes=-5),
    ) -> uuid.UUID:
        transition_at = (
            datetime.now(UTC) + transition_offset
            if transition_offset is not None
            else None
        )
        async with sessionmaker() as session:
            event = Event(
                club_id=uuid.uuid4(),
                created_by=uuid.uuid4(),
                title="Test Event",
                location=WKTElement("POINT(153.0137 -27.4975)", srid=4326),
                starts_at=datetime.now(UTC) + timedelta(days=7),
                is_free=True,
                visibility=visibility,
                transition_at=transition_at,
            )
            session.add(event)
            await session.commit()
            return event.id

    return _make_event
