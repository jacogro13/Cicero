from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from types import TracebackType
from typing import Self

from cicero.domain.document.ports.chapter_read_model import ChapterReadModel
from cicero.domain.document.ports.document_repository import DocumentRepository
from cicero.domain.document.ports.summary_read_model import SummaryReadModel
from cicero.domain.messages import Event


class UnitOfWork(ABC):
    """Port: the transaction boundary (ADR-003).

    An async context manager exposing the repositories and read-model stores a
    transaction spans (``uow.documents``, ``uow.chapters``, ``uow.summaries``).
    Commit is explicit; any other exit rolls back.
    """

    documents: DocumentRepository
    chapters: ChapterReadModel
    summaries: SummaryReadModel

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    def collect_new_events(self) -> Iterator[Event]:
        """Drain domain events off the aggregates touched in this transaction (ADR-011)."""
        for document in list(self.documents.seen.values()):
            yield from document.collect_events()


UnitOfWorkFactory = Callable[[], UnitOfWork]
"""Zero-arg callable returning a fresh, unentered :class:`UnitOfWork`, so one use
case can open several sequential transactions."""
