from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.messages import Event


@dataclass(frozen=True)
class DocumentUploaded(Event):
    """A document's source file has been stored and its metadata persisted (ADR-011)."""

    document_id: DocumentId


@dataclass(frozen=True)
class ExtractionCompleted(Event):
    """A document's source was extracted to Markdown and it is now READY (ADR-012)."""

    document_id: DocumentId


@dataclass(frozen=True)
class ExtractionFailed(Event):
    """Extracting a document's source failed and it is now FAILED (ADR-012)."""

    document_id: DocumentId
