"""The read side: queries that bypass the message bus (ADR-015).

Each opens a read-only transaction off ``uow_factory`` and returns a read model,
never a domain aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass

import anyio

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

#: Seconds the whole content read may take, however many chapters it spans (ADR-034).
#: Well above a healthy book — the blobs are Markdown off a nearby store — and far
#: below the hours a stalling backend would otherwise buy itself.
CONTENT_READ_DEADLINE = 60.0


@dataclass(frozen=True)
class DocumentView:
    """A document as the browsing surface sees it; the enrichment fields are
    best-effort and may stay unset (ADR-026/027/028)."""

    id: DocumentId
    title: str
    status: DocumentStatus
    kind: DocumentKind
    source_url: str | None
    authors: str | None
    year: int | None
    has_cover: bool


@dataclass(frozen=True)
class SummaryView:
    """A document's summary text (ADR-016)."""

    text: str


@dataclass(frozen=True)
class ChapterView:
    """One chapter; ``summary`` is ``None`` until it has been summarised (ADR-021)."""

    index: int
    title: str
    summary: str | None


async def _require_document(uow: UnitOfWork, document_id: DocumentId) -> Document:
    """The document, or :class:`DocumentNotFound`. Every per-document read runs this
    first, so "no such document" never arrives disguised as an empty projection —
    the read models are keyed by id and answer for an unknown one too (ADR-008/021).
    """
    document = await uow.documents.find_by_id(document_id)
    if document is None:
        raise DocumentNotFound(document_id)
    return document


async def list_documents(uow_factory: UnitOfWorkFactory) -> list[DocumentView]:
    """Every stored document."""
    async with uow_factory() as uow:
        documents = await uow.documents.find_all()
    return [
        DocumentView(
            id=d.id,
            title=d.title,
            status=d.status,
            kind=d.kind,
            source_url=d.source_url,
            authors=d.authors,
            year=d.year,
            has_cover=d.has_cover,
        )
        for d in documents
    ]


async def get_document_summary(
    uow_factory: UnitOfWorkFactory, document_id: DocumentId
) -> SummaryView | None:
    """The per-chapter summaries joined in order, or ``None`` if it has none yet.
    Raises :class:`DocumentNotFound` for an unknown id."""
    async with uow_factory() as uow:
        await _require_document(uow, document_id)
        summaries = await uow.summaries.all(document_id)
    if not summaries:
        return None
    text = "\n\n".join(summaries[index] for index in sorted(summaries))
    return SummaryView(text=text)


async def get_document_chapters(
    uow_factory: UnitOfWorkFactory, document_id: DocumentId
) -> list[ChapterView]:
    """The table of contents zipped with per-chapter summaries; empty until the
    document has chapters (ADR-021). Raises :class:`DocumentNotFound` for an
    unknown id."""
    async with uow_factory() as uow:
        await _require_document(uow, document_id)
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
    deadline: float = CONTENT_READ_DEADLINE,
) -> str | None:
    """The chapter blobs assembled under their titles, or ``None`` until the document
    has chapters (ADR-019). Raises :class:`DocumentNotFound` for an unknown id, and
    ``TimeoutError`` if the blobs together outrun ``deadline``."""
    async with uow_factory() as uow:
        document = await _require_document(uow, document_id)
        titles = await uow.chapters.list(document_id)
    if not titles:
        return None
    # One GET per chapter, so a slow store multiplies by the chapter count: the deadline
    # is on the whole loop, bounding the request rather than each blob (ADR-034).
    with anyio.fail_after(deadline):
        sections = [
            f"# {title}\n\n{(await storage.get(document.chapter_key(index))).decode('utf-8')}"
            for index, title in enumerate(titles)
        ]
    return "\n\n".join(sections)


async def get_document_file(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    document_id: DocumentId,
) -> bytes | None:
    """The original source file, or ``None`` for a URL document, which has no source
    blob (ADR-027). Raises :class:`DocumentNotFound` for an unknown id."""
    async with uow_factory() as uow:
        document = await _require_document(uow, document_id)
    if document.source_url is not None:
        return None
    return await storage.get(document.source_key)


async def get_document_cover(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    document_id: DocumentId,
) -> bytes | None:
    """The cover image bytes, or ``None`` when the document has no cover — enrichment
    is best-effort, so it may never get one (ADR-028). Raises
    :class:`DocumentNotFound` for an unknown id."""
    async with uow_factory() as uow:
        document = await _require_document(uow, document_id)
    if not document.has_cover:
        return None
    return await storage.get(document.cover_key)
