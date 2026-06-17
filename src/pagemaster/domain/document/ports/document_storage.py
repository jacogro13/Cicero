from abc import ABC, abstractmethod


class DocumentStorage(ABC):
    """Port: object storage for a document's files (ADR-004).

    Reached from a use case, never constructed directly; objects are addressed
    by key (a document derives its own via :attr:`Document.source_key`). ``get``
    / ``delete`` arrive in the batches that need them.
    """

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Store ``data`` at ``key``, overwriting any existing object."""
        ...
