from dataclasses import dataclass

from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.messages import Event


@dataclass(frozen=True)
class DocumentUploaded(Event):
    """A document's source file has been stored and its metadata persisted (ADR-011)."""

    document_id: DocumentId
