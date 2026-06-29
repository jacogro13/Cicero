"""Integration fixtures: real infra in throwaway containers (ADR-006, ADR-007).

Each container starts once per session; per-test isolation is a fresh Postgres
schema (built from the adapter's mapped metadata) and a uniquely-named S3 bucket,
so committed rows and stored objects never leak between tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from uuid import uuid4

import boto3
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

from cicero.adapters.persistence.orm import metadata, start_mappers
from cicero.adapters.persistence.unit_of_work import make_sqlalchemy_uow_factory
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory


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


@pytest.fixture(scope="session")
def minio_config() -> Iterator[dict[str, str]]:
    """A real MinIO in a throwaway container, as `S3DocumentStorage` kwargs."""
    with MinioContainer() as minio:
        config = minio.get_config()
        yield {
            "endpoint_url": f"http://{config['endpoint']}",
            "access_key_id": config["access_key"],
            "secret_access_key": config["secret_key"],
            "region_name": "us-east-1",
        }


def _boto_client(config: dict[str, str]):
    return boto3.client(
        "s3",
        endpoint_url=config["endpoint_url"],
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
        region_name=config["region_name"],
    )


@pytest.fixture
def s3_bucket(minio_config: dict[str, str]) -> str:
    """A fresh, empty bucket per test — the adapter assumes its bucket exists."""
    bucket = f"test-{uuid4().hex}"
    _boto_client(minio_config).create_bucket(Bucket=bucket)
    return bucket


@pytest.fixture
def read_object(minio_config: dict[str, str], s3_bucket: str) -> Callable[[str], bytes]:
    """Read an object back through a separate client, to assert what `put` stored."""
    client = _boto_client(minio_config)

    def read(key: str) -> bytes:
        return client.get_object(Bucket=s3_bucket, Key=key)["Body"].read()

    return read
