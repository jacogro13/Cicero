from __future__ import annotations

from functools import partial

import anyio
import boto3
from botocore.exceptions import ClientError

from cicero.domain.document.exceptions import BlobNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage

# create_bucket on a bucket this client already owns is a success, not an error.
_BUCKET_EXISTS = {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}
# A missing object: MinIO/AWS answer NoSuchKey, some gateways only the bare 404.
_NO_SUCH_KEY = {"NoSuchKey", "404"}


class S3DocumentStorage(DocumentStorage):
    """`DocumentStorage` over any S3-compatible store — Garage/MinIO/AWS (ADR-007).

    boto3 is synchronous, so every call is offloaded to an anyio worker thread.
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

    async def ensure_bucket(self) -> None:
        """Create the bucket if absent — idempotent startup provisioning (ADR-010)."""
        await anyio.to_thread.run_sync(self._ensure_bucket_sync)

    def _ensure_bucket_sync(self) -> None:
        try:
            self._client.create_bucket(Bucket=self._bucket)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in _BUCKET_EXISTS:
                raise

    async def put(self, key: str, data: bytes) -> None:
        call = partial(self._client.put_object, Bucket=self._bucket, Key=key, Body=data)
        await anyio.to_thread.run_sync(call)

    async def get(self, key: str) -> bytes:
        # The streaming body read is network I/O too, so it runs in the thread.
        return await anyio.to_thread.run_sync(partial(self._get_sync, key))

    def _get_sync(self, key: str) -> bytes:
        try:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as exc:
            # Translate the one failure the port declares; anything else is this
            # store misbehaving and belongs to the caller as-is (ADR-004).
            if exc.response.get("Error", {}).get("Code") in _NO_SUCH_KEY:
                raise BlobNotFound(key) from exc
            raise

    async def delete(self, key: str) -> None:
        # S3 delete_object is idempotent: deleting an absent key still succeeds.
        call = partial(self._client.delete_object, Bucket=self._bucket, Key=key)
        await anyio.to_thread.run_sync(call)

    async def delete_prefix(self, prefix: str) -> None:
        await anyio.to_thread.run_sync(partial(self._delete_prefix_sync, prefix))

    def _delete_prefix_sync(self, prefix: str) -> None:
        # List, then delete one key at a time: delete_object is portable across S3
        # backends (ADR-007), where batch delete_objects needs a Content-MD5 header
        # MinIO rejects. A document holds few blobs, so per-key cost is negligible.
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                self._client.delete_object(Bucket=self._bucket, Key=obj["Key"])
