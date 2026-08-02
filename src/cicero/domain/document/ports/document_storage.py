from abc import ABC, abstractmethod

from cicero.domain.document.exceptions import BlobNotFound


class DocumentStorage(ABC):
    """Port: object storage for a document's files, addressed by key (ADR-004)."""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Store ``data`` at ``key``, overwriting any existing object."""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the bytes stored at ``key``.

        :raises BlobNotFound: nothing is stored there. Deletes are idempotent and
            reads are not, because a caller only reads a key the metadata says
            exists — so an absent object is a broken invariant worth raising on.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object at ``key``; a no-op if it is absent."""
        ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Remove every object whose key starts with ``prefix``; a no-op if none do."""
        ...


__all__ = ["BlobNotFound", "DocumentStorage"]
