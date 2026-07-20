from abc import ABC, abstractmethod

from cicero.domain.document.document_id import DocumentId


class SummaryReadModel(ABC):
    """Port: the denormalized store of document summaries (ADR-016).

    The summarisation stage writes it (in the same transaction as ``mark_summarised``,
    so ``SUMMARISED`` ⇔ readable); the read side serves it. Keyed by document and
    decoupled from the ``Document`` aggregate, so the read shape can diverge from the
    write model. Reached through ``uow.summaries``; the owning UoW controls commit.
    """

    @abstractmethod
    async def save(self, document_id: DocumentId, text: str) -> None:
        """Upsert a document's summary text (a re-run overwrites)."""
        ...

    @abstractmethod
    async def get(self, document_id: DocumentId) -> str | None:
        """A document's summary text, or ``None`` if it has none."""
        ...
