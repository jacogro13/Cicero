from abc import ABC, abstractmethod


class DocumentStorage(ABC):
    """Port: object-storage operations for a document's files (ADR-004).

    A collection-like interface over object storage, not a vendor client:
    callers reach it from a use case and never construct it directly. Concrete
    adapters (in-memory now, an S3-compatible backend later) implement it in the
    outer layers. Objects are addressed by a storage key; a document derives its
    own key via :attr:`Document.source_key`. ``get`` and ``delete`` are added in
    the batches that need them (serving the original file, deleting a document).
    """

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Store ``data`` at ``key``, overwriting any existing object."""
        ...
