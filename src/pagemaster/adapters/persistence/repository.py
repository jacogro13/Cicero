from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.ports.document_repository import DocumentRepository


class PostgresDocumentRepository(DocumentRepository):
    """``DocumentRepository`` over a SQLAlchemy ``AsyncSession`` (ADR-006).

    Reached through ``uow.documents``; the owning UoW controls commit/rollback.
    ``save`` adds to the session identity map (insert / tracked update); flushing
    and committing belong to the UoW.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: dict[DocumentId, Document] = {}

    async def save(self, document: Document) -> None:
        self._session.add(document)
        self.seen[document.id] = document

    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        document = await self._session.get(Document, document_id)
        if document is not None:
            self.seen[document.id] = document
        return document

    async def find_all(self) -> list[Document]:
        documents = list(await self._session.scalars(select(Document)))
        self.seen.update({document.id: document for document in documents})
        return documents

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
