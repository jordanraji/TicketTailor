"""Async Redis client for the RSVP atomic counter (ADR-0005).

The counter (`rsvp:count:{event_id}`) is the live read path that avoids
contending on a relational row under spike load. PostgreSQL remains the system
of record: the counter is seeded read-through from a `COUNT(*)` on a cache
miss, and a reconciliation job (ADR-0008) corrects any drift.

Per ADR-0005's failure mode, callers degrade gracefully when Redis is
unavailable - they fall back to the database count rather than failing the
request. `RedisCounter` therefore swallows connection errors on its read/write
paths and signals "unavailable" so the service layer can choose the fallback.
"""

import uuid
from collections.abc import AsyncIterator

from redis import RedisError
from redis.asyncio import Redis

from tickettailor.shared.config import settings

_COUNT_KEY = "rsvp:count:{event_id}"


def _count_key(event_id: uuid.UUID) -> str:
    return _COUNT_KEY.format(event_id=event_id)


class RedisClient:
    """Thin wrapper owning the async connection pool for the process."""

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        # Socket timeouts make a half-open connection (e.g. during an
        # ElastiCache failover) raise RedisError quickly instead of hanging the
        # event loop, so RsvpCounter can fall back to the DB count (ADR-0005).
        # health_check_interval revalidates idle pooled connections.
        self.client: Redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=30,
        )

    async def close(self) -> None:
        await self.client.aclose()


class RsvpCounter:
    """Atomic RSVP attendee counter backed by Redis (ADR-0005).

    All methods return ``None`` when Redis is unreachable so the service layer
    can fall back to the PostgreSQL count and preserve correctness.
    """

    def __init__(self, client: Redis) -> None:
        self.client = client

    async def increment(self, event_id: uuid.UUID) -> int | None:
        try:
            return int(await self.client.incr(_count_key(event_id)))
        except RedisError:
            return None

    async def decrement(self, event_id: uuid.UUID) -> int | None:
        try:
            # Counts are clamped at zero: a decrement below zero is corrected so
            # a transiently-out-of-sync key can't surface a negative count.
            new_value = int(await self.client.decr(_count_key(event_id)))
            if new_value < 0:
                await self.client.set(_count_key(event_id), 0)
                return 0
            return new_value
        except RedisError:
            return None

    async def get(self, event_id: uuid.UUID) -> int | None:
        try:
            value = await self.client.get(_count_key(event_id))
        except RedisError:
            return None
        if value is None:
            return None
        return int(value)

    async def seed(self, event_id: uuid.UUID, count: int) -> None:
        """Seed the counter from the authoritative DB count on a cache miss.

        Uses ``SET NX`` so a concurrent increment that lands first is not
        sent back to the snapshot value.
        """
        try:
            await self.client.set(_count_key(event_id), count, nx=True)
        except RedisError:
            return

    async def overwrite(self, event_id: uuid.UUID, count: int) -> int | None:
        """Force the counter to ``count``, overwriting any existing value.

        Unlike :meth:`seed` this does *not* use ``SET NX`` - it is the write
        path for the reconciliation job (ADR-0005, ADR-0008), which has
        recomputed the authoritative count from PostgreSQL and must correct a
        drifted key even when it already holds a (wrong) value. Returns the
        value written, or ``None`` if Redis is unreachable.
        """
        try:
            await self.client.set(_count_key(event_id), count)
            return count
        except RedisError:
            return None

    async def scan_event_ids(self) -> AsyncIterator[uuid.UUID]:
        """Yield the event id of every live counter key (``rsvp:count:*``).

        Used by the reconciliation job to enumerate the events that currently
        have a counter, without coupling to the events module. Keys whose
        suffix is not a valid UUID are skipped defensively. Silently yields
        nothing if Redis is unreachable - reconciliation is a best-effort
        backstop, not a request-path operation.
        """
        pattern = _COUNT_KEY.format(event_id="*")
        try:
            async for key in self.client.scan_iter(match=pattern):
                suffix = key.rsplit(":", 1)[-1]
                try:
                    yield uuid.UUID(suffix)
                except ValueError:
                    continue
        except RedisError:
            return
