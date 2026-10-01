"""QA4-input / AR2 - property-based fuzzing against the OpenAPI contract.

Schemathesis reads the app's own OpenAPI schema and generates malformed and
boundary inputs for every operation. The asserted property is the QA4-input
claim: **no input causes a server error** - a 5xx means an input-validation gap
(an unhandled exception reaching the user) rather than a clean 4xx rejection.

The app is served by a real uvicorn instance bound to the testcontainers
Postgres/Redis. Running a live server (rather than the in-process ASGI
transport) keeps every request on a single event loop - the app's async DB and
Redis pools are loop-bound, so a fresh-loop-per-request transport would crash
them with "attached to a different loop" and mask the actual property.

Every request carries a validly-signed token (minted directly -
`require_current_user_id` does no DB lookup) so authenticated operations are
fuzzed past the auth gate instead of stopping at 401.

Only the ``not_a_server_error`` check runs: the API deliberately returns
problem+json error bodies whose 4xx codes are not all declared in the schema, so
full response-schema conformance (AR2) is a separate concern that would flag
those documented-by-design error shapes.
"""

import socket
import threading
import time
import uuid
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import pytest
import schemathesis
import schemathesis.pytest
import uvicorn
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tickettailor.main import app
from tickettailor.shared.app_services import (
    app_services,
    get_db_session,
    get_replica_db_session,
)
from tickettailor.shared.redis import RedisClient
from tickettailor.shared.security import create_access_token

# A valid signed token for an arbitrary subject; the auth dependency only
# decodes the JWT, so the user need not exist for fuzzing to pass the gate.
_AUTH_HEADERS = {"Authorization": f"Bearer {create_access_token(uuid.uuid4())}"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def live_server(database_url: str, redis_url: str) -> Iterator[str]:
    """Serve the app via uvicorn in a thread, wired to the test containers.

    One server = one event loop, so the app's loop-bound async DB/Redis pools
    stay consistent across every fuzzed request.
    """
    # pool_pre_ping validates a pooled connection before use: the engine is
    # reused across the whole fuzz run, so this prevents a transient stale
    # connection from surfacing as a spurious 5xx.
    engine = create_async_engine(database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

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
    app_services.redis = RedisClient(redis_url=redis_url)

    port = _free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
    )
    server = uvicorn.Server(config)
    # uvicorn already skips signal-handler installation off the main thread.
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("uvicorn did not start in time")
            time.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.dependency_overrides.clear()
        app_services.redis = None


@pytest.fixture(scope="module")
def api_schema(live_server: str) -> Any:
    # /healthz and /readyz are marked include_in_schema=False in the app, so
    # they never appear here and are not fuzzed (a readiness 503 is by design,
    # not a server error). See the probe definitions in main.py.
    return schemathesis.openapi.from_url(f"{live_server}/openapi.json")


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
@settings(
    max_examples=30,
    deadline=None,
    # Deterministic input generation: a fixed seed makes this a stable CI gate
    # rather than a roll of the dice each run.
    derandomize=True,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        # Some operations filter many generated inputs (e.g. method negatives);
        # we only assert "never 5xx", so heavy filtering is acceptable here.
        HealthCheck.filter_too_much,
    ],
)
def test_no_input_causes_a_server_error(case: Any) -> None:
    case.call_and_validate(headers=_AUTH_HEADERS, checks=[not_a_server_error])
