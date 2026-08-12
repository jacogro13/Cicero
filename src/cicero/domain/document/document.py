from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.domain.document.events import (
    DocumentProcessingFailed,
    DocumentRetried,
    DocumentUploaded,
    ExtractionCompleted,
)
from cicero.domain.document.exceptions import (
    DocumentNotRetryable,
    InvalidDocumentTitle,
    InvalidDocumentUrl,
)
from cicero.domain.messages import Event


@dataclass
class Document:
    """A library document aggregate. Build via :meth:`create` or
    :meth:`create_from_url`; change status through the ``mark_*`` methods (ADR-002)."""

    id: DocumentId
    title: str
    status: DocumentStatus = DocumentStatus.UPLOADED
    kind: DocumentKind = DocumentKind.BOOK
    source_url: str | None = None
    # The enrichment branch (ADR-028): a best-effort axis independent of ``status``.
    enrichment_status: EnrichmentStatus = EnrichmentStatus.PENDING
    authors: str | None = None
    year: int | None = None
    has_cover: bool = False

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
    def create(cls, title: str, kind: DocumentKind = DocumentKind.BOOK) -> Document:
        if not title.strip():
            raise InvalidDocumentTitle("title must not be empty")
        document = cls(id=DocumentId.new(), title=title, kind=kind)
        document.events.append(DocumentUploaded(document_id=document.id))
        return document

    @classmethod
    def create_from_url(
        cls, url: str, kind: DocumentKind = DocumentKind.ARTICLE
    ) -> Document:
        """A document whose source is the link itself, with no blob — raises
        ``InvalidDocumentUrl`` for anything but http(s) (ADR-027)."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InvalidDocumentUrl(f"not an http(s) URL: {url!r}")
        document = cls(
            id=DocumentId.new(),
            title=_title_from_url(parsed),
            kind=kind,
            source_url=url,
        )
        document.events.append(DocumentUploaded(document_id=document.id))
        return document

    def set_kind(self, kind: DocumentKind) -> None:
        self.kind = kind

    @property
    def source_key(self) -> str:
        return self._storage_key("source")

    @property
    def storage_prefix(self) -> str:
        """Prefix covering every blob of this document — deleting it sweeps them all."""
        return f"documents/{self.id.value}/"

    def chapter_key(self, index: int) -> str:
        return self._storage_key(f"chapters/{index}")

    @property
    def cover_key(self) -> str:
        return self._storage_key("cover")

    def _storage_key(self, name: str) -> str:
        """The storage layout, a pure function of identity: ``documents/{id}/{name}`` (ADR-004)."""
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

    def retry(self) -> None:
        """Return a failed document to the start of the spine (ADR-030). Guarded, unlike
        the ``mark_*`` methods: its caller is a person, so a wrong call is a client
        error — raises ``DocumentNotRetryable``."""
        if self.status is not DocumentStatus.FAILED:
            raise DocumentNotRetryable(self.id, self.status)
        self.status = DocumentStatus.UPLOADED
        self.events.append(DocumentRetried(document_id=self.id))

    def mark_enriching(self) -> None:
        self.enrichment_status = EnrichmentStatus.ENRICHING

    def apply_enrichment(
        self, *, authors: str | None, year: int | None, has_cover: bool
    ) -> None:
        self.authors = authors
        self.year = year
        self.has_cover = has_cover

    def mark_enriched(self) -> None:
        self.enrichment_status = EnrichmentStatus.ENRICHED

    def mark_enrichment_failed(self) -> None:
        """Terminal on the enrichment branch only — ``status`` is untouched, so the
        document stays as readable as before (ADR-028)."""
        self.enrichment_status = EnrichmentStatus.FAILED


def _title_from_url(parsed) -> str:
    """A starting title from a URL: the last path segment humanized, or the host
    when there is no path."""
    segments = [segment for segment in parsed.path.split("/") if segment]
    if segments:
        words = segments[-1].rsplit(".", 1)[0].replace("-", " ").replace("_", " ").split()
        if words:
            return " ".join(word.capitalize() for word in words)
    return parsed.netloc
