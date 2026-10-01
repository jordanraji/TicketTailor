from collections.abc import AsyncGenerator

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.shared.config import settings
from tickettailor.shared.database import PostgreSQLClient
from tickettailor.shared.redis import RedisClient


class AppServices(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    primary_db: PostgreSQLClient | None = None
    replica_db: PostgreSQLClient | None = None
    redis: RedisClient | None = None

    def get_primary_db(self) -> PostgreSQLClient:
        if not self.primary_db:
            self.primary_db = PostgreSQLClient(
                database_url=settings.DATABASE_URL,
                echo=False,
            )
        return self.primary_db

    def get_replica_db(self) -> PostgreSQLClient:
        if not self.replica_db:
            self.replica_db = PostgreSQLClient(
                database_url=settings.DATABASE_REPLICA_URL,
                echo=False,
            )
        return self.replica_db

    def get_redis(self) -> RedisClient:
        if not self.redis:
            self.redis = RedisClient(redis_url=settings.REDIS_URL)
        return self.redis


app_services = AppServices()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with app_services.get_primary_db().get_db() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_replica_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with app_services.get_replica_db().get_db() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
