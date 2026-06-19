from __future__ import annotations

from functools import partial

import anyio
import boto3

from pagemaster.domain.document.ports.document_storage import DocumentStorage


class S3DocumentStorage(DocumentStorage):
    """`DocumentStorage` over any S3-compatible store — Garage/MinIO/AWS (ADR-007).

    boto3 is synchronous, so every call is offloaded to the anyio worker thread to
    keep the event loop free. The bucket is assumed to exist (provisioned by the
    composition root / compose init), as the Postgres adapter assumes its schema does.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region_name: str,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )

    async def put(self, key: str, data: bytes) -> None:
        call = partial(self._client.put_object, Bucket=self._bucket, Key=key, Body=data)
        await anyio.to_thread.run_sync(call)

    async def get(self, key: str) -> bytes:
        # The streaming body read is network I/O too, so it runs in the thread.
        return await anyio.to_thread.run_sync(partial(self._get_sync, key))

    def _get_sync(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    async def delete(self, key: str) -> None:
        # S3 delete_object is idempotent: deleting an absent key still succeeds.
        call = partial(self._client.delete_object, Bucket=self._bucket, Key=key)
        await anyio.to_thread.run_sync(call)
