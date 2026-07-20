from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.messages import Event


@dataclass(frozen=True)
class DocumentEvent(Event):
    """A fact about one document. The shared ``document_id`` is what lets a single
    handler advance the pipeline off any stage's event (ADR-014)."""

    document_id: DocumentId


@dataclass(frozen=True)
class DocumentUploaded(DocumentEvent):
    """A document's source file has been stored and its metadata persisted (ADR-011)."""


@dataclass(frozen=True)
class ExtractionCompleted(DocumentEvent):
    """A document's source was extracted to Markdown and it is now EXTRACTED (ADR-012)."""


@dataclass(frozen=True)
class DocumentProcessingFailed(DocumentEvent):
    """A document failed at some pipeline stage and is now FAILED — stage-agnostic,
    matching the single ``FAILED`` terminal (ADR-014/016)."""
