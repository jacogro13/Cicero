from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.messages import Command


@dataclass(frozen=True)
class UploadDocument(Command):
    """Store a source file under a new document and persist its metadata (ADR-011).

    ``kind`` overrides the source-derived default (BOOK for a PDF) when set (ADR-026).
    """

    title: str
    content: bytes
    kind: DocumentKind | None = None


@dataclass(frozen=True)
class IngestUrl(Command):
    """Ingest a web article by URL — no file, the link is the source (ADR-027).

    ``kind`` overrides the source-derived default (ARTICLE) when set (ADR-026).
    """

    url: str
    kind: DocumentKind | None = None


@dataclass(frozen=True)
class SetDocumentKind(Command):
    """Correct a document's browsing classification (ADR-026)."""

    document_id: DocumentId
    kind: DocumentKind


@dataclass(frozen=True)
class DeleteDocument(Command):
    """Remove a document and its source file (ADR-012)."""

    document_id: DocumentId


@dataclass(frozen=True)
class ExtractDocument(Command):
    """Extract a document's source to Markdown — issued by the job-queue worker (ADR-013)."""

    document_id: DocumentId


@dataclass(frozen=True)
class SummariseDocument(Command):
    """Summarise a document's extracted text — issued by the job-queue worker (ADR-016)."""

    document_id: DocumentId
