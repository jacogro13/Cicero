"""In-memory ``DocumentStorage`` double for unit tests — a dict keyed by storage
key (ADR-004); ``get`` joined the port for extraction (ADR-009).
"""

from __future__ import annotations

from cicero.domain.document.exceptions import BlobNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage


class InMemoryDocumentStorage(DocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self.objects if k.startswith(prefix)]:
            del self.objects[key]

    async def get(self, key: str) -> bytes:
        # Raises what the S3 adapter raises, not KeyError: a double looser than its
        # adapter is how the read side ships a 500 nobody predicted.
        if key not in self.objects:
            raise BlobNotFound(key)
        return self.objects[key]
