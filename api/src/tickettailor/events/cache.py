import hashlib
import json
import uuid
from decimal import Decimal

from redis.asyncio import Redis


class EventGeoCache:
    """Helper class to handle caching of geo-radius search results in Redis.

    Encapsulates stable key generation, serialization of list tuples, and
    graceful degradation on Redis connection failures.
    """

    def __init__(self, redis_client: Redis) -> None:
        self.redis_client = redis_client

    def build_key(
        self,
        latitude: Decimal,
        longitude: Decimal,
        radius_m: float,
        limit: int,
        category: str | None,
    ) -> str:
        """Construct a stable, deterministic cache key based on search parameters."""
        lat_str = f"{float(latitude):.6f}"
        lng_str = f"{float(longitude):.6f}"
        cat_str = category or ""
        input_str = (
            f"lat:{lat_str};lng:{lng_str};"
            f"radius:{radius_m};limit:{limit};category:{cat_str}"
        )
        param_hash = hashlib.md5(  # nosec B324
            input_str.encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        return f"events:geo:{param_hash}"

    async def get(self, key: str) -> list[tuple[uuid.UUID, float]] | None:
        """Retrieve cached list of (event_id, distance_m) pairs.

        Returns None on cache miss or error to degrade gracefully.
        """
        try:
            data = await self.redis_client.get(key)
            if data is None:
                return None
            parsed = json.loads(data)
            return [(uuid.UUID(item[0]), float(item[1])) for item in parsed]
        except Exception:  # nosec B110
            return None

    async def set(
        self, key: str, results: list[tuple[uuid.UUID, float]], ttl: int = 30
    ) -> None:
        """Cache list of (event_id, distance_m) pairs with a given TTL.

        Swallows errors silently to degrade gracefully.
        """
        try:
            payload = [[str(eid), dist] for eid, dist in results]
            await self.redis_client.set(key, json.dumps(payload), ex=ttl)
        except Exception:  # nosec B110
            pass
