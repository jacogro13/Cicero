from abc import ABC, abstractmethod

from cicero.domain.document.document_id import DocumentId


class SummaryReadModel(ABC):
    """Port: the denormalized store of document summaries, reached through
    ``uow.summaries`` (ADR-016). The summarisation stage writes it; the read side serves it.
    """

    @abstractmethod
    async def save(self, document_id: DocumentId, text: str) -> None:
        """Upsert a document's summary text (a re-run overwrites)."""
        ...

    @abstractmethod
    async def get(self, document_id: DocumentId) -> str | None:
        """A document's summary text, or ``None`` if it has none."""
        ...
