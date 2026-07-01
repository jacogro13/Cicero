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
class ListDocuments(Command):
    """Return every stored document — a read that rides the bus (ADR-012)."""
