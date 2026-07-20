"""The read side: queries that bypass the message bus (ADR-015).

Each function opens a short read-only transaction off the ``uow_factory`` and returns
a **read model**, never a domain aggregate — so a view's shape can diverge from the
write model as the reader experience grows. This first phase still reads through the
aggregate repository; a denormalized read model arrives only where a view needs it.
"""

from __future__ import annotations

from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class DocumentView:
    """Read model of a document: identity, title, pipeline status. Decoupled from the
    domain ``Document`` (the write model) and the ``DocumentResponse`` wire DTO."""

    id: DocumentId
    title: str
    status: DocumentStatus


async def list_documents(uow_factory: UnitOfWorkFactory) -> list[DocumentView]:
    """Every stored document, as read models. No command, no commit (ADR-015)."""
    async with uow_factory() as uow:
        documents = await uow.documents.find_all()
    return [
        DocumentView(id=d.id, title=d.title, status=d.status) for d in documents
    ]
