import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from tickettailor.auth.routers import router as auth_router
from tickettailor.calendar.routers import (
    router as calendar_router,
)
from tickettailor.calendar.routers import (
    router_events as calendar_events_router,
)
from tickettailor.events.routers import router as events_router
from tickettailor.organisers.routers import router as organisers_router
from tickettailor.organisers.service import club_exists_validator
from tickettailor.rsvp.routers import router as rsvp_router
from tickettailor.shared.app_services import app_services
from tickettailor.shared.club_validator import register_club_validator
from tickettailor.shared.config import settings
from tickettailor.shared.database import PostgreSQLClient
from tickettailor.shared.exceptions import TicketTailorError
from tickettailor.shared.logging import CorrelationIdMiddleware, setup_logging
from tickettailor.shared.redis import RedisClient
from tickettailor.users.routers import router as users_router

setup_logging()

register_club_validator(club_exists_validator)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app_services.primary_db = PostgreSQLClient(
        database_url=settings.DATABASE_URL,
        echo=False,
    )
    app_services.replica_db = PostgreSQLClient(
        database_url=settings.DATABASE_REPLICA_URL,
        echo=False,
    )
    app_services.redis = RedisClient(redis_url=settings.REDIS_URL)
    yield
    if app_services.primary_db:
        await app_services.primary_db.engine.dispose()
    if app_services.replica_db:
        await app_services.replica_db.engine.dispose()
    if app_services.redis:
        await app_services.redis.close()


app = FastAPI(
    title="TicketTailor API",
    description="CSSE6400 TicketTailor API",
    version="0.0.1",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)

# CORS for the SPA frontend. Origins are env-driven (CORS_ALLOWED_ORIGINS,
# comma-separated) so dev (localhost) and prod differ by config, not code.
cors_origins = [
    origin.strip()
    for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(TicketTailorError)
async def ticket_tailor_exception_handler(
    request: Request, exc: TicketTailorError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
        },
        headers={"Content-Type": "application/problem+json"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    """Return 422 for invalid requests without echoing the raw input.

    FastAPI's default handler embeds the offending input in the response body.
    That input can contain characters that are not JSON-encodable - notably a
    lone UTF-16 surrogate - which crashes the error response itself into a 500.
    We re-serialise the (loc, msg, type) of each error with ``ensure_ascii=True``
    so any such character is escaped, and drop the raw input entirely.
    """
    errors: list[dict[str, Any]] = [
        {
            "type": err.get("type"),
            "loc": list(err.get("loc", ())),
            "msg": err.get("msg"),
        }
        for err in exc.errors()
    ]
    body = json.dumps({"detail": errors}, ensure_ascii=True)
    return Response(content=body, status_code=422, media_type="application/json")


app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(calendar_events_router)
app.include_router(events_router)
app.include_router(organisers_router)
app.include_router(rsvp_router)
app.include_router(users_router)


@app.get("/healthz", status_code=200, include_in_schema=False)
async def health_check() -> dict[str, str]:
    """Liveness probe: cheap and dependency-free.

    Deliberately does not touch Postgres or Redis so a transient datastore
    blip does not cause ECS to kill an otherwise-healthy task. Readiness (is
    this task fit to receive traffic) is the separate /readyz probe below.
    """
    return {"status": "healthy", "service": "tickettailor-api"}


@app.get("/readyz", include_in_schema=False)
async def readiness_check() -> JSONResponse:
    """Readiness probe: gates traffic on the primary DB being reachable.

    Excluded from the OpenAPI schema (include_in_schema=False): the probes are
    operational, take no input, and /readyz returns 503 by design when a
    dependency is down - a legitimate readiness signal, not an API operation.
    Keeping them out of the schema also keeps the schemathesis input-fuzzing
    contract test (which builds from /openapi.json) from treating that 503 as a
    server error.

    The ALB target group points here so a task whose connection pool is
    exhausted or whose migrations failed is taken out of rotation instead of
    silently sinking requests during a load test. Each dependency check is
    bounded by a short timeout so the probe itself can never hang.

    Redis is checked but is NOT a readiness gate: the RSVP path degrades to the
    DB count when Redis is unreachable (ADR-0005), so a Redis outage must not
    pull every task out of the ALB. Only the primary database is fatal here.
    """
    checks: dict[str, str] = {}
    ready = True

    async def _check_db() -> None:
        async with app_services.get_primary_db().get_db() as session:
            await session.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_check_db(), timeout=2.0)
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - any DB failure means not-ready
        checks["database"] = f"error: {type(exc).__name__}"
        ready = False

    try:
        await asyncio.wait_for(app_services.get_redis().client.ping(), timeout=2.0)
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001 - informational; degrades to DB count
        checks["redis"] = f"degraded: {type(exc).__name__}"

    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
