from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cicero.adapters.persistence.orm import summaries
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.summary_read_model import SummaryReadModel


class PostgresSummaryReadModel(SummaryReadModel):
    """``SummaryReadModel`` over a SQLAlchemy ``AsyncSession`` (ADR-016/021).

    Uses Core statements over the ``summaries`` table, not the aggregate mapping.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document_id: DocumentId, chapter_index: int, text: str) -> None:
        # Upsert: a re-run (SUMMARISING → SummariseDocument) overwrites the summary.
        statement = insert(summaries).values(
            document_id=document_id, position=chapter_index, text=text
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[summaries.c.document_id, summaries.c.position],
                set_={"text": text},
            )
        )

    async def get(self, document_id: DocumentId, chapter_index: int) -> str | None:
        return await self._session.scalar(
            select(summaries.c.text).where(
                summaries.c.document_id == document_id,
                summaries.c.position == chapter_index,
            )
        )

    async def all(self, document_id: DocumentId) -> dict[int, str]:
        rows = await self._session.execute(
            select(summaries.c.position, summaries.c.text).where(
                summaries.c.document_id == document_id
            )
        )
        return {position: text for position, text in rows}

    async def delete(self, document_id: DocumentId) -> None:
        await self._session.execute(
            delete(summaries).where(summaries.c.document_id == document_id)
        )
