from abc import ABC, abstractmethod

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId


class DocumentRepository(ABC):
    """Port: the collection of ``Document`` aggregates (ADR-003).

    Reached through a :class:`UnitOfWork` (``uow.documents``), never constructed
    directly. Implementations track the aggregates they have ``seen`` (saved or
    fetched) so the UoW can drain their events after a commit (ADR-011).
    """

    seen: dict[DocumentId, Document]

    @abstractmethod
    async def save(self, document: Document) -> None:
        """Insert or update a document record (and mark it seen)."""
        ...

    @abstractmethod
    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        """Return the document with the given id, or ``None`` if absent."""
        ...

    @abstractmethod
    async def find_all(self) -> list[Document]:
        """Return all documents (empty list if none)."""
        ...

    @abstractmethod
    async def delete(self, document: Document) -> None:
        """Remove a document record."""
        ...
