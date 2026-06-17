"""In-memory test double for the ``DocumentStorage`` port.

Stores objects in a plain dict keyed by storage key, so unit tests can exercise
the upload use case with no real object storage. ``put`` is the production port
method (ADR-004); ``get`` is a read-back helper for assertions, not part of the
port yet. Batch #8 swaps in a real S3-compatible adapter behind the same port,
leaving the upload behaviour unchanged.
"""

from __future__ import annotations

from pagemaster.domain.document.ports.document_storage import DocumentStorage


class InMemoryDocumentStorage(DocumentStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        """Read back a stored object (test helper, not part of the port yet)."""
        return self.objects[key]
