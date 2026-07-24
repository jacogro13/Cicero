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


@dataclass(frozen=True)
class ChapterView:
    """Read model of one chapter: its position, title, and summary (ADR-021).

    ``summary`` is ``None`` until the chapter has been summarised.
    """

    index: int
    title: str
    summary: str | None


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
    """A document's summary for admin inspection — the per-chapter summaries joined
    in order — or ``None`` if it has none yet (ADR-016/021)."""
    async with uow_factory() as uow:
        summaries = await uow.summaries.all(document_id)
    if not summaries:
        return None
    text = "\n\n".join(summaries[index] for index in sorted(summaries))
    return SummaryView(text=text)


async def get_document_chapters(
    uow_factory: UnitOfWorkFactory, document_id: DocumentId
) -> list[ChapterView]:
    """The reader's table of contents zipped with per-chapter summaries (ADR-021).

    Empty when the document has no chapters yet; a chapter's ``summary`` is ``None``
    until it has been summarised.
    """
    async with uow_factory() as uow:
        titles = await uow.chapters.list(document_id)
        summaries = await uow.summaries.all(document_id)
    return [
        ChapterView(index=index, title=title, summary=summaries.get(index))
        for index, title in enumerate(titles)
    ]


async def get_document_content(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    document_id: DocumentId,
) -> str | None:
    """The extracted Markdown for admin inspection — the chapter blobs assembled
    under their titles — or ``None`` until the document has chapters (ADR-019/021).

    Raises :class:`DocumentNotFound` for an unknown id.
    """
    async with uow_factory() as uow:
        document = await uow.documents.find_by_id(document_id)
        if document is None:
            raise DocumentNotFound(document_id)
        titles = await uow.chapters.list(document_id)
    if not titles:
        return None
    sections = [
        f"# {title}\n\n{(await storage.get(document.chapter_key(index))).decode('utf-8')}"
        for index, title in enumerate(titles)
    ]
    return "\n\n".join(sections)


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
