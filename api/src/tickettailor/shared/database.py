from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tickettailor.shared.config import settings


class PostgreSQLClient:
    def __init__(self, database_url: str, echo: bool = False):
        self.database_url = database_url
        self.echo = echo
        self.engine: AsyncEngine = self.create_engine()
        self.sessionmaker = self.create_sessionmaker()

    def create_engine(self) -> AsyncEngine:
        # Pool sizing is bounded so an autoscaled fleet cannot exhaust RDS
        # max_connections (see config DB_POOL_SIZE / DB_MAX_OVERFLOW).
        # pool_pre_ping discards connections broken by an RDS failover before
        # handing them out, and pool_recycle caps idle-connection lifetime.
        # asyncpg command_timeout bounds a single round-trip; statement_timeout
        # (a server setting) bounds query execution so neither can pin a
        # pooled connection indefinitely under load.
        return create_async_engine(
            self.database_url,
            echo=self.echo,
            future=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
            connect_args={
                "command_timeout": settings.DB_COMMAND_TIMEOUT_SECONDS,
                "server_settings": {
                    "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
                },
            },
        )

    def create_sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def get_db(self) -> AsyncIterator[AsyncSession]:
        session = self.sessionmaker()
        try:
            yield session
        finally:
            await session.close()
