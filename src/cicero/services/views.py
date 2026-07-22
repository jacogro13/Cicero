"""The read side: queries that bypass the message bus (ADR-015).

Each opens a read-only transaction off ``uow_factory`` and returns a read model,
never a domain aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory

# The extracted Markdown blob (content_key) exists from EXTRACTED onwards (ADR-019).
_EXTRACTED_STATUSES = frozenset(
    {
        DocumentStatus.EXTRACTED,
        DocumentStatus.SUMMARISING,
        DocumentStatus.SUMMARISED,
    }
)


@dataclass(frozen=True)
class DocumentView:
    """Read model of a document: identity, title, pipeline status (ADR-015)."""

    id: DocumentId
    title: str
    status: DocumentStatus


@dataclass(frozen=True)
class SummaryView:
    """Read model of a document's summary — the read experience (ADR-016)."""

    text: str


async def list_documents(uow_factory: UnitOfWorkFactory) -> list[DocumentView]:
    """Every stored document, as read models. No command, no commit (ADR-015)."""
    async with uow_factory() as uow:
        documents = await uow.documents.find_all()
    return [
        DocumentView(id=d.id, title=d.title, status=d.status) for d in documents
    ]


async def get_document_summary(
    uow_factory: UnitOfWorkFactory, document_id: DocumentId
) -> SummaryView | None:
    """A document's summary, or ``None`` if it has none yet (ADR-016)."""
    async with uow_factory() as uow:
        text = await uow.summaries.get(document_id)
    return SummaryView(text=text) if text is not None else None


async def get_document_content(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    document_id: DocumentId,
) -> str | None:
    """The extracted Markdown from storage, or ``None`` until the document is
    ``EXTRACTED`` — a blob read via the storage port, not a projection (ADR-019).

    Raises :class:`DocumentNotFound` for an unknown id.
    """
    async with uow_factory() as uow:
        document = await uow.documents.find_by_id(document_id)
    if document is None:
        raise DocumentNotFound(document_id)
    if document.status not in _EXTRACTED_STATUSES:
        return None
    return (await storage.get(document.content_key)).decode("utf-8")


async def get_document_file(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    document_id: DocumentId,
) -> bytes:
    """The original source file from storage, present from ``UPLOADED`` (ADR-019).

    Raises :class:`DocumentNotFound` for an unknown id.
    """
    async with uow_factory() as uow:
        document = await uow.documents.find_by_id(document_id)
    if document is None:
        raise DocumentNotFound(document_id)
    return await storage.get(document.source_key)
