from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.document_repository import DocumentRepository


class PostgresDocumentRepository(DocumentRepository):
    """``DocumentRepository`` over a SQLAlchemy ``AsyncSession`` (ADR-006).

    ``save`` adds to the session identity map; the owning UoW flushes and commits.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    async def _save(self, document: Document) -> None:
        self._session.add(document)

    async def _find_by_id(self, document_id: DocumentId) -> Document | None:
        return await self._session.get(Document, document_id)

    async def _find_all(self) -> list[Document]:
        # Ordered in SQL: unordered, Postgres returns heap order, and every pipeline
        # stage is an UPDATE that moves the row to the end of it.
        return list(await self._session.scalars(select(Document).order_by(Document.title)))

    async def _delete(self, document: Document) -> None:
        await self._session.delete(document)
