from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import Self

from pagemaster.domain.document.ports.document_repository import DocumentRepository


class UnitOfWork(ABC):
    """Port: the transaction boundary (ADR-003).

    An async context manager exposing one repository per aggregate
    (``uow.documents``, later ``uow.notes`` / …) so one block commits across all
    of them atomically. Commit is explicit; any other exit rolls back.
    """

    documents: DocumentRepository

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


UnitOfWorkFactory = Callable[[], UnitOfWork]
"""Zero-arg callable returning a fresh, *unentered* :class:`UnitOfWork`.

Services take the factory (not an instance) so one use case can open several
sequential transactions.
"""
