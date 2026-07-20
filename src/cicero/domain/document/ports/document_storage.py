from abc import ABC, abstractmethod


class DocumentStorage(ABC):
    """Port: object storage for a document's files, addressed by key (ADR-004)."""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Store ``data`` at ``key``, overwriting any existing object."""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the bytes stored at ``key`` (ADR-009: extraction reads the source)."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object at ``key``; a no-op if it is absent."""
        ...
