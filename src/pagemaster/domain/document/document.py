from __future__ import annotations

from dataclasses import dataclass

from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.document_status import DocumentStatus


@dataclass
class Document:
    """A library document.

    Construct via :meth:`create` so the id is generated and the title is
    validated; do not instantiate directly. Status changes go through the
    ``mark_*`` methods rather than assigning :attr:`status` directly (ADR-002).
    """

    id: DocumentId
    title: str
    status: DocumentStatus = DocumentStatus.UPLOADED
    #: Opaque locator for the document's extracted text — the internal raw
    #: material used to generate AI summaries, never shown to the user directly.
    #: ``None`` until the document is READY; set atomically with the status by
    #: :meth:`mark_ready`.
    content_key: str | None = None

    @classmethod
    def create(cls, title: str) -> Document:
        if not title.strip():
            raise ValueError("title must not be empty")
        return cls(id=DocumentId.new(), title=title)

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING

    def mark_ready(self, content_key: str) -> None:
        self.status = DocumentStatus.READY
        self.content_key = content_key

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
