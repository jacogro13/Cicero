from __future__ import annotations

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.exceptions import DomainError


class InvalidDocumentTitle(DomainError):
    """A document title fails its rule (e.g. empty). Maps to 422 (ADR-008)."""


class InvalidDocumentUrl(DomainError):
    """An ingest URL is not a valid http(s) link. Maps to 422 (ADR-008/027)."""


class DocumentNotFound(DomainError):
    """No document exists for the given id. Maps to 404 (ADR-008)."""

    def __init__(self, document_id: DocumentId) -> None:
        super().__init__(f"document {document_id.value} not found")


class DocumentNotRetryable(DomainError):
    """Only a FAILED document can be re-driven. Maps to 409 (ADR-008/030)."""

    def __init__(self, document_id: DocumentId, status: DocumentStatus) -> None:
        super().__init__(f"document {document_id.value} is {status.value}, not FAILED")


class ArticleExtractionFailed(DomainError):
    """The ``ArticleExtractor`` port could not fetch a page or found no article text
    in it. Declared here so a caller can name it without importing an adapter
    (ADR-008/027); unmapped, since only background stages call the port."""


class BlobNotFound(DomainError):
    """The ``DocumentStorage`` port has no object at the key. Unmapped on purpose —
    metadata pointing at a missing blob is a broken invariant, not a client error,
    so it surfaces as 500 (ADR-004/008)."""

    def __init__(self, key: str) -> None:
        super().__init__(f"no object stored at {key!r}")
