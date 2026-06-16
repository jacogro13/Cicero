from abc import ABC, abstractmethod

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId


class DocumentRepository(ABC):
    """Port: persistence operations for the ``Document`` aggregate (ADR-003).

    A collection-like interface, not a database session: callers reach it
    through a :class:`UnitOfWork` (``uow.documents``) and never
    construct it directly. Concrete adapters (in-memory now, Postgres later)
    implement it in the outer layers. ``find_all`` and ``delete`` are added in
    the batches that need them.
    """

    @abstractmethod
    async def save(self, document: Document) -> None:
        """Insert or update a document record."""
        ...

    @abstractmethod
    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        """Return the document with the given id, or ``None`` if absent."""
        ...
