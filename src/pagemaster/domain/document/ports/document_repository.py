from abc import ABC, abstractmethod

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId


class DocumentRepository(ABC):
    """Port: the collection of ``Document`` aggregates (ADR-003).

    Reached through a :class:`UnitOfWork` (``uow.documents``), never constructed
    directly. ``find_all`` / ``delete`` arrive in the batches that need them.
    """

    @abstractmethod
    async def save(self, document: Document) -> None:
        """Insert or update a document record."""
        ...

    @abstractmethod
    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        """Return the document with the given id, or ``None`` if absent."""
        ...
