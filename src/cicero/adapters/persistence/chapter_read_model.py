from __future__ import annotations

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from cicero.adapters.persistence.orm import chapters
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.chapter_read_model import ChapterReadModel


class PostgresChapterReadModel(ChapterReadModel):
    """``ChapterReadModel`` over a SQLAlchemy ``AsyncSession`` (ADR-021).

    Core statements over the ``chapters`` table, not an aggregate mapping.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document_id: DocumentId, titles: list[str]) -> None:
        # Replace: a re-extraction overwrites the whole table of contents.
        await self._session.execute(
            delete(chapters).where(chapters.c.document_id == document_id)
        )
        if titles:
            await self._session.execute(
                insert(chapters),
                [
                    {"document_id": document_id, "position": position, "title": title}
                    for position, title in enumerate(titles)
                ],
            )

    async def list(self, document_id: DocumentId) -> list[str]:
        titles = await self._session.scalars(
            select(chapters.c.title)
            .where(chapters.c.document_id == document_id)
            .order_by(chapters.c.position)
        )
        return list(titles)
