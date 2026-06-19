from __future__ import annotations

from dataclasses import dataclass

from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.document_status import DocumentStatus
from pagemaster.domain.document.exceptions import InvalidDocumentTitle


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

    @classmethod
    def create(cls, title: str) -> Document:
        if not title.strip():
            raise InvalidDocumentTitle("title must not be empty")
        return cls(id=DocumentId.new(), title=title)

    @property
    def source_key(self) -> str:
        """Storage key for the original source file (ADR-004)."""
        return self._storage_key("source")

    @property
    def content_key(self) -> str:
        """Storage key for the extracted text — internal, never shown to the
        reader (ADR-004). The text exists only once :attr:`status` is READY
        (ADR-002); the key itself is just the identity-derived address."""
        return self._storage_key("content")

    def _storage_key(self, name: str) -> str:
        """Object-storage layout, a pure function of identity: ``documents/{id}/{name}``."""
        return f"documents/{self.id.value}/{name}"

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING

    def mark_ready(self) -> None:
        self.status = DocumentStatus.READY

    def mark_failed(self) -> None:
        self.status = DocumentStatus.FAILED
