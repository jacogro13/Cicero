from abc import ABC, abstractmethod

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId


class DocumentRepository(ABC):
    """Port: the collection of ``Document`` aggregates, reached through ``uow.documents``
    (ADR-003).

    Records every aggregate touched in ``seen`` for event draining (ADR-011);
    implementations supply persistence via the ``_``-prefixed hooks.
    """

    def __init__(self) -> None:
        self.seen: dict[DocumentId, Document] = {}

    async def save(self, document: Document) -> None:
        """Insert or update a document record."""
        await self._save(document)
        self.seen[document.id] = document

    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        """Return the document with the given id, or ``None`` if absent."""
        document = await self._find_by_id(document_id)
        if document is not None:
            self.seen[document.id] = document
        return document

    async def find_all(self) -> list[Document]:
        """Return all documents (empty list if none)."""
        documents = await self._find_all()
        for document in documents:
            self.seen[document.id] = document
        return documents

    async def delete(self, document: Document) -> None:
        """Remove a document record. The aggregate is still seen — a deletion
        can raise events of its own."""
        await self._delete(document)
        self.seen[document.id] = document

    @abstractmethod
    async def _save(self, document: Document) -> None: ...

    @abstractmethod
    async def _find_by_id(self, document_id: DocumentId) -> Document | None: ...

    @abstractmethod
    async def _find_all(self) -> list[Document]: ...

    @abstractmethod
    async def _delete(self, document: Document) -> None: ...
