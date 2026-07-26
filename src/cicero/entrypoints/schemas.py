from __future__ import annotations

import uuid

from pydantic import BaseModel

from cicero.domain.document.document import Document
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.services.views import ChapterView, DocumentView, SummaryView


class DocumentResponse(BaseModel):
    """Wire shape of a document (ADR-005): identity, title, status, kind (ADR-026)."""

    id: uuid.UUID
    title: str
    status: DocumentStatus
    kind: DocumentKind

    @classmethod
    def from_domain(cls, document: Document) -> DocumentResponse:
        """From the write model — a create/upload echoes the affected aggregate."""
        return cls(
            id=document.id.value,
            title=document.title,
            status=document.status,
            kind=document.kind,
        )

    @classmethod
    def from_view(cls, view: DocumentView) -> DocumentResponse:
        """From the read model (ADR-015) — the list endpoint maps it to the wire DTO."""
        return cls(
            id=view.id.value, title=view.title, status=view.status, kind=view.kind
        )


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
