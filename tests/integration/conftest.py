"""Integration fixtures: a real Postgres in a throwaway container (ADR-006).

The container starts once per session; each test gets a fresh schema (built from
the adapter's mapped metadata) so committed rows never leak between tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from pagemaster.adapters.persistence.orm import metadata, start_mappers
from pagemaster.adapters.persistence.unit_of_work import make_sqlalchemy_uow_factory
from pagemaster.domain.ports.unit_of_work import UnitOfWorkFactory


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
async def uow_factory(postgres_url: str) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(postgres_url)
    start_mappers()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    # expire_on_commit=False keeps a returned Document usable after its UoW exits.
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield make_sqlalchemy_uow_factory(session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()
