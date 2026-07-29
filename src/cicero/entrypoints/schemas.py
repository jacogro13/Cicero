from __future__ import annotations

import uuid

from pydantic import BaseModel

from cicero.domain.document.document import Document
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.services.views import ChapterView, DocumentView, SummaryView


class DocumentResponse(BaseModel):
    """Wire shape of a document (ADR-005): identity, title, status, kind, source, and the
    best-effort enrichment — authors, year, whether a cover exists (ADR-026/027/028)."""

    id: uuid.UUID
    title: str
    status: DocumentStatus
    kind: DocumentKind
    source_url: str | None = None
    authors: str | None = None
    year: int | None = None
    has_cover: bool = False

    @classmethod
    def from_domain(cls, document: Document) -> DocumentResponse:
        """From the write model — a create/upload/ingest echoes the affected aggregate."""
        return cls(
            id=document.id.value,
            title=document.title,
            status=document.status,
            kind=document.kind,
            source_url=document.source_url,
            authors=document.authors,
            year=document.year,
            has_cover=document.has_cover,
        )

    @classmethod
    def from_view(cls, view: DocumentView) -> DocumentResponse:
        """From the read model (ADR-015) — the list endpoint maps it to the wire DTO."""
        return cls(
            id=view.id.value,
            title=view.title,
            status=view.status,
            kind=view.kind,
            source_url=view.source_url,
            authors=view.authors,
            year=view.year,
            has_cover=view.has_cover,
        )


class IngestUrlRequest(BaseModel):
    """Wire shape of a URL ingest (ADR-027): the article's link, optional kind override."""

    url: str
    kind: DocumentKind | None = None


class UpdateDocumentRequest(BaseModel):
    """Wire shape of a document correction (ADR-026): the new browsing kind."""

    kind: DocumentKind


class SummaryResponse(BaseModel):
    """Wire shape of a document's summary — the read experience (ADR-016)."""

    text: str

    @classmethod
    def from_view(cls, view: SummaryView) -> SummaryResponse:
        return cls(text=view.text)


class ChapterResponse(BaseModel):
    """Wire shape of a chapter — the reader's table of contents (ADR-021)."""

    index: int
    title: str
    summary: str | None

    @classmethod
    def from_view(cls, view: ChapterView) -> ChapterResponse:
        return cls(index=view.index, title=view.title, summary=view.summary)
