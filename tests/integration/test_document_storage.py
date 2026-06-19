"""The DocumentStorage port, verified against a real S3-compatible store (ADR-007).

`put` lands the exact bytes at the key and overwrites an existing object — the
in-memory double's contract, now proven against MinIO over the wire.
"""

import pytest
from botocore.exceptions import ClientError

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

    async def test_get_returns_the_stored_bytes(self, storage):
        await storage.put("documents/abc123/source", b"%PDF-1.4 source bytes")

        assert await storage.get("documents/abc123/source") == b"%PDF-1.4 source bytes"

    async def test_delete_removes_the_object(self, storage, read_object):
        await storage.put("documents/abc123/source", b"%PDF-1.4 source bytes")

        await storage.delete("documents/abc123/source")

        with pytest.raises(ClientError):
            read_object("documents/abc123/source")

    async def test_delete_is_a_no_op_for_a_missing_object(self, storage):
        await storage.delete("documents/never-stored/source")
