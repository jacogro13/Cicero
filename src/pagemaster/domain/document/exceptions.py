from __future__ import annotations

from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.exceptions import DomainError


class InvalidDocumentTitle(DomainError):
    """A document title fails its rule (e.g. empty). Maps to 422 (ADR-008)."""


class DocumentNotFound(DomainError):
    """No document exists for the given id. Maps to 404 (ADR-008)."""

    def __init__(self, document_id: DocumentId) -> None:
        super().__init__(f"document {document_id.value} not found")
