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
    #: Locator for the extracted text (internal, never shown to the reader);
    #: ``None`` until set with the status by :meth:`mark_ready` (ADR-002).
    content_key: str | None = None

    @classmethod
    def create(cls, title: str) -> Document:
        if not title.strip():
            raise ValueError("title must not be empty")
        return cls(id=DocumentId.new(), title=title)

    @property
    def source_key(self) -> str:
        """Storage key for the original source file, derived from identity
        (ADR-004). Distinct from :attr:`content_key` (the extracted text)."""
        return f"documents/{self.id.value}/source"

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING

    def mark_ready(self, content_key: str) -> None:
        self.status = DocumentStatus.READY
        self.content_key = content_key

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
