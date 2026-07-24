from abc import ABC, abstractmethod

from cicero.domain.document.document_id import DocumentId


class ChapterReadModel(ABC):
    """Port: a document's ordered chapter titles — its table of contents (ADR-021),
    reached through ``uow.chapters``. Extraction writes it; the read side and the
    summariser read it. Chapter *content* lives in object storage, not here.
    """

    @abstractmethod
    async def save(self, document_id: DocumentId, titles: list[str]) -> None:
        """Replace a document's ordered chapter titles (a re-extraction overwrites)."""
        ...

    @abstractmethod
    async def list(self, document_id: DocumentId) -> list[str]:
        """A document's chapter titles in order, or ``[]`` if it has none."""
        ...
