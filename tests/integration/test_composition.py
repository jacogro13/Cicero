"""The composition root, end to end (ADR-010).

The app is driven through its real lifespan — **no ``dependency_overrides``** — over
a real Postgres and a real MinIO, with the seams of ADR-005/006/007 retired. Entering
the ``TestClient`` context runs startup, which must provision the schema and the
bucket from settings alone; a POST then GET round-trips through the live stack, and
the source blob is read back from storage to prove the bucket was provisioned and hit.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import boto3
import pytest
from fastapi.testclient import TestClient

from cicero.entrypoints.main import create_app
from cicero.entrypoints.settings import get_settings

_PDF = ("clean-code.pdf", b"%PDF-1.4 bytes", "application/pdf")


@pytest.fixture
def live_stack(postgres_url: str, minio_config: dict[str, str], monkeypatch) -> Iterator[dict]:
    """Point the process at the containers via the environment Settings reads, on a
    fresh bucket the app has never seen — so startup must create it. The engine
    singleton is disposed by the lifespan; the settings cache is cleared either side."""
    bucket = f"pm-{uuid4().hex}"
    env = {
        "DATABASE_URL": postgres_url,
        "S3_ENDPOINT_URL": minio_config["endpoint_url"],
        "S3_ACCESS_KEY_ID": minio_config["access_key_id"],
        "S3_SECRET_ACCESS_KEY": minio_config["secret_access_key"],
        "S3_BUCKET": bucket,
        "S3_REGION": minio_config["region_name"],
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield {"bucket": bucket, "minio_config": minio_config}
    get_settings.cache_clear()


def _read_source(minio_config: dict[str, str], bucket: str, document_id: str) -> bytes:
    client = boto3.client(
        "s3",
        endpoint_url=minio_config["endpoint_url"],
        aws_access_key_id=minio_config["access_key_id"],
        aws_secret_access_key=minio_config["secret_access_key"],
        region_name=minio_config["region_name"],
    )
    key = f"documents/{document_id}/source"
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()


def test_live_app_provisions_and_round_trips(live_stack: dict):
    with TestClient(create_app()) as client:  # __enter__ runs the lifespan
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        listed = client.get("/api/documents").json()

    # Persisted to real Postgres and read back through the live app.
    assert created["id"] in [doc["id"] for doc in listed]
    # The bucket was provisioned at startup and the source blob actually landed.
    assert _read_source(live_stack["minio_config"], live_stack["bucket"], created["id"]) == _PDF[1]
