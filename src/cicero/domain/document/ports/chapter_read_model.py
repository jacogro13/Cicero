from abc import ABC, abstractmethod

from cicero.domain.document.document_id import DocumentId


class ChapterReadModel(ABC):
    """Port: a document's ordered chapter titles, reached through ``uow.chapters``
    (ADR-021). Chapter *content* lives in object storage, not here."""

    @abstractmethod
    async def save(self, document_id: DocumentId, titles: list[str]) -> None:
        """Replace a document's ordered chapter titles (a re-extraction overwrites)."""
        ...

    @abstractmethod
    async def list(self, document_id: DocumentId) -> list[str]:
        """A document's chapter titles in order, or ``[]`` if it has none."""
        ...

    @abstractmethod
    async def delete(self, document_id: DocumentId) -> None:
        """Drop a document's chapter titles — a no-op if it has none."""
        ...
