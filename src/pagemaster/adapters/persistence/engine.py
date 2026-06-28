"""SQLAlchemy engine, session factory, and schema provisioning (ADR-006, ADR-010).

The composition root owns one engine per process. ``create_schema`` is the
turnkey-startup alternative to migrations: idempotent ``create_all`` while this app
solely owns the schema (Alembic deferred — ADR-010).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pagemaster.adapters.persistence.orm import metadata, start_mappers


def make_engine(database_url: str) -> AsyncEngine:
    # pool_pre_ping discards a connection that died while idle instead of raising
    # on the next use; pool_recycle retires connections before the server would.
    return create_async_engine(database_url, pool_pre_ping=True, pool_recycle=1800)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False keeps a returned Document usable after its UoW exits.
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_schema(engine: AsyncEngine) -> None:
    """Map the domain and create its tables if absent — idempotent (ADR-010)."""
    start_mappers()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
