"""The DocumentStorage port, verified against a real S3-compatible store (ADR-007).

`put` lands the exact bytes at the key and overwrites an existing object — the
in-memory double's contract, now proven against MinIO over the wire.
"""

import pytest

from pagemaster.adapters.storage.s3 import S3DocumentStorage


@pytest.fixture
def storage(minio_config: dict[str, str], s3_bucket: str) -> S3DocumentStorage:
    return S3DocumentStorage(bucket=s3_bucket, **minio_config)


class TestS3DocumentStorage:
    async def test_put_stores_the_bytes_at_the_key(self, storage, read_object):
        await storage.put("documents/abc123/source", b"%PDF-1.4 source bytes")

        assert read_object("documents/abc123/source") == b"%PDF-1.4 source bytes"

    async def test_put_overwrites_an_existing_object(self, storage, read_object):
        await storage.put("documents/abc123/source", b"first")
        await storage.put("documents/abc123/source", b"second")

        assert read_object("documents/abc123/source") == b"second"
