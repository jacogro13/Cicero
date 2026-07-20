from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cicero.adapters.persistence.orm import summaries
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.summary_read_model import SummaryReadModel


class PostgresSummaryReadModel(SummaryReadModel):
    """``SummaryReadModel`` over a SQLAlchemy ``AsyncSession`` (ADR-016).

    Uses Core statements over the ``summaries`` table, not the aggregate mapping.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document_id: DocumentId, text: str) -> None:
        # Upsert: a re-run (SUMMARISING → SummariseDocument) overwrites the summary.
        statement = insert(summaries).values(document_id=document_id, text=text)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[summaries.c.document_id], set_={"text": text}
            )
        )

    async def get(self, document_id: DocumentId) -> str | None:
        return await self._session.scalar(
            select(summaries.c.text).where(summaries.c.document_id == document_id)
        )
