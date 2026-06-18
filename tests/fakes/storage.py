"""In-memory ``DocumentStorage`` double for unit tests — a dict keyed by storage
key. ``put`` is the port; ``get`` is a read-back helper for assertions (ADR-004).
"""

from __future__ import annotations

from pagemaster.domain.document.ports.document_storage import DocumentStorage


class InMemoryDocumentStorage(DocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def get(self, key: str) -> bytes:
        """Read back a stored object (test helper, not part of the port yet)."""
        return self.objects[key]
