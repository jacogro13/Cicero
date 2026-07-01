from __future__ import annotations

from dataclasses import dataclass

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import (
    DocumentUploaded,
    ExtractionCompleted,
    ExtractionFailed,
)
from cicero.domain.document.exceptions import InvalidDocumentTitle
from cicero.domain.messages import Event


@dataclass
class Document:
    """A library document.

    Construct via :meth:`create` so the id is generated and the title is
    validated; do not instantiate directly. Status changes go through the
    ``mark_*`` methods rather than assigning :attr:`status` directly (ADR-002).
    The aggregate records domain events off its lifecycle (ADR-011); the
    Unit of Work drains them after a commit.
    """

    id: DocumentId
    title: str
    status: DocumentStatus = DocumentStatus.UPLOADED

    @property
    def events(self) -> list[Event]:
        """Pending domain events. Lazily created so ORM-loaded instances (built
        without ``__init__``) work; not a field, so it stays out of equality."""
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
    def content_key(self) -> str:
        """Storage key for the extracted text — internal, never shown to the reader (ADR-004)."""
        return self._storage_key("content")

    def _storage_key(self, name: str) -> str:
        """Object-storage layout, a pure function of identity: ``documents/{id}/{name}``."""
        return f"documents/{self.id.value}/{name}"

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING

    def mark_ready(self) -> None:
        self.status = DocumentStatus.READY
        self.events.append(ExtractionCompleted(document_id=self.id))

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
        self.events.append(ExtractionFailed(document_id=self.id))
