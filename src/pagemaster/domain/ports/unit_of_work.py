from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import Self

from pagemaster.domain.document.ports.document_repository import DocumentRepository


class UnitOfWork(ABC):
    """Port: the transactional boundary for the application (ADR-003).

    The Unit of Work is the *transaction scope*, not an aggregate's collection:
    it exposes one repository per aggregate as an attribute (``uow.documents``,
    and later ``uow.notes`` / ``uow.chat`` as those aggregates land) so a single
    ``async with uow:`` block can commit changes across several aggregates
    together. Each block is one transaction — durable on normal exit after
    :meth:`commit`, rolled back otherwise. Concrete implementations live in the
    outer layers.
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
"""A zero-arg callable returning a fresh, *unentered* ``UnitOfWork``.

Services accept the factory (not a single instance) so one use case can open
multiple sequential transactions — e.g. a background job that needs the upload
transaction to commit before its first read.
"""
