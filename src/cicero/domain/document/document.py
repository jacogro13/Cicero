from __future__ import annotations

from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import (
    DocumentProcessingFailed,
    DocumentUploaded,
    ExtractionCompleted,
)
from cicero.domain.document.exceptions import InvalidDocumentTitle
from cicero.domain.messages import Event


@dataclass
class Document:
    """A library document aggregate.

    Build via :meth:`create`; change status through the ``mark_*`` methods
    (ADR-002/014). Records domain events the UoW drains after commit (ADR-011).
    """

    id: DocumentId
    title: str
    status: DocumentStatus = DocumentStatus.UPLOADED

    @property
    def events(self) -> list[Event]:
        """Pending domain events; lazy so ORM-loaded instances work and equality ignores them."""
        if not hasattr(self, "_events"):
            self._events: list[Event] = []
        return self._events

    def collect_events(self) -> list[Event]:
        """Return the pending events and clear them."""
        collected = self.events[:]
        self.events.clear()
        return collected

    @classmethod
    def create(cls, title: str) -> Document:
        if not title.strip():
            raise InvalidDocumentTitle("title must not be empty")
        document = cls(id=DocumentId.new(), title=title)
        document.events.append(DocumentUploaded(document_id=document.id))
        return document

    @property
    def source_key(self) -> str:
        """Storage key for the original source file (ADR-004)."""
        return self._storage_key("source")

    @property
    def storage_prefix(self) -> str:
        """Key prefix under which all of a document's blobs live — deleting it removes
        the source and every chapter blob in one sweep (ADR-004)."""
        return f"documents/{self.id.value}/"

    def chapter_key(self, index: int) -> str:
        """Storage key for a chapter's extracted Markdown — internal, never shown
        to the reader (ADR-021)."""
        return self._storage_key(f"chapters/{index}")

    def _storage_key(self, name: str) -> str:
        """Object-storage layout, a pure function of identity: ``documents/{id}/{name}``."""
        return f"documents/{self.id.value}/{name}"

    def mark_extracting(self) -> None:
        self.status = DocumentStatus.EXTRACTING

    def mark_extracted(self) -> None:
        self.status = DocumentStatus.EXTRACTED
        self.events.append(ExtractionCompleted(document_id=self.id))

    def mark_summarising(self) -> None:
        self.status = DocumentStatus.SUMMARISING

    def mark_summarised(self) -> None:
        self.status = DocumentStatus.SUMMARISED

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
        self.events.append(DocumentProcessingFailed(document_id=self.id))
