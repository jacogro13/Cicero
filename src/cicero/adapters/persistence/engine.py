"""SQLAlchemy engine and session factory (ADR-006). Schema provisioning moved to
Alembic migrations (ADR-024); deadlines and pool budget are stated in ADR-033."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@dataclass(frozen=True)
class EnginePolicy:
    """What a connection is allowed to cost: ``command_timeout`` seconds per statement
    and ``connect_timeout`` to open the connection, over a pool of ``pool_size`` plus
    ``max_overflow`` burst, waiting ``pool_timeout`` for a free one (ADR-033)."""

    command_timeout: float = 30.0
    connect_timeout: float = 10.0
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0


DEFAULT_ENGINE = EnginePolicy()


def make_engine(database_url: str, policy: EnginePolicy = DEFAULT_ENGINE) -> AsyncEngine:
    # pool_pre_ping discards a connection that died while idle instead of raising
    # on the next use; pool_recycle retires connections before the server would.
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=policy.pool_size,
        max_overflow=policy.max_overflow,
        pool_timeout=policy.pool_timeout,
        # asyncpg's own kwargs: without command_timeout it has no statement deadline
        # at all, and a hung query holds its request or job worker forever.
        connect_args={
            "command_timeout": policy.command_timeout,
            "timeout": policy.connect_timeout,
        },
    )


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False keeps a returned Document usable after its UoW exits.
    return async_sessionmaker(engine, expire_on_commit=False)
