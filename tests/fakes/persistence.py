"""In-memory test doubles for the document persistence ports.

These fakes let unit tests exercise the ``DocumentRepository`` /
``UnitOfWork`` contract with no real database. Writes are buffered in
the Unit of Work and flushed to a shared in-memory store on ``commit``; an exit
without ``commit`` rolls back. So the fakes honour the transaction boundary —
uncommitted writes are invisible to other transactions. Batch #7 swaps in a
real Postgres adapter behind the same ports, leaving this behaviour unchanged.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.ports.document_repository import DocumentRepository
from pagemaster.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


class InMemoryDocumentRepository(DocumentRepository):
    """Backed by a shared ``store`` dict, with a per-transaction write buffer.

    ``save`` stages into the buffer; ``find_by_id`` reads the buffer first
    (read-your-writes) then the committed store. The owning Unit of Work
    flushes the buffer into the store on commit and discards it on rollback.
    """

    def __init__(self, store: dict[DocumentId, Document]) -> None:
        self._store = store
        self._pending: dict[DocumentId, Document] = {}

    async def save(self, document: Document) -> None:
        self._pending[document.id] = document

    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        if document_id in self._pending:
            return self._pending[document_id]
        return self._store.get(document_id)

    def flush(self) -> None:
        self._store.update(self._pending)
        self._pending.clear()

    def discard(self) -> None:
        self._pending.clear()


class InMemoryUnitOfWork(UnitOfWork):
    """One ``async with`` block is one transaction over the shared store."""

    def __init__(self, store: dict[DocumentId, Document]) -> None:
        self.documents = InMemoryDocumentRepository(store)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Rollback by default: commit() must be explicit, so any writes not
        # committed in this block are discarded — on a clean exit or on error.
        # rollback() after a commit() is a no-op (the buffer is already empty).
        await self.rollback()

    async def commit(self) -> None:
        self.documents.flush()

    async def rollback(self) -> None:
        self.documents.discard()


def make_in_memory_uow_factory(
    store: dict[DocumentId, Document] | None = None,
) -> UnitOfWorkFactory:
    """Return a zero-arg factory yielding fresh UoWs over one shared store.

    All UoWs from a given factory see the same committed data, so tests can
    write in one transaction and read it back in another.
    """
    backing_store: dict[DocumentId, Document] = {} if store is None else store

    def factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(backing_store)

    return factory
