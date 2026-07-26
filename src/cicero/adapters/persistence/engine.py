"""SQLAlchemy engine and session factory (ADR-006). Schema provisioning moved to
Alembic migrations (ADR-024)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(database_url: str) -> AsyncEngine:
    # pool_pre_ping discards a connection that died while idle instead of raising
    # on the next use; pool_recycle retires connections before the server would.
    return create_async_engine(database_url, pool_pre_ping=True, pool_recycle=1800)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False keeps a returned Document usable after its UoW exits.
    return async_sessionmaker(engine, expire_on_commit=False)
