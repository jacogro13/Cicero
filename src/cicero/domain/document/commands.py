from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.messages import Command


@dataclass(frozen=True)
class UploadDocument(Command):
    """Store a source file under a new document and persist its metadata (ADR-011)."""

    title: str
    content: bytes


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
