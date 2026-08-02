from abc import ABC, abstractmethod

from cicero.domain.document.document_id import DocumentId


class SummaryReadModel(ABC):
    """Port: per-chapter summaries, reached through ``uow.summaries`` (ADR-016/021)."""

    @abstractmethod
    async def save(self, document_id: DocumentId, chapter_index: int, text: str) -> None:
        """Upsert a chapter's summary text (a re-run overwrites)."""
        ...

    @abstractmethod
    async def get(self, document_id: DocumentId, chapter_index: int) -> str | None:
        """A chapter's summary text, or ``None`` if it has none."""
        ...

    @abstractmethod
    async def all(self, document_id: DocumentId) -> dict[int, str]:
        """Every chapter summary of a document, keyed by chapter index."""
        ...

    @abstractmethod
    async def delete(self, document_id: DocumentId) -> None:
        """Drop every chapter summary of a document — a no-op if it has none."""
        ...
