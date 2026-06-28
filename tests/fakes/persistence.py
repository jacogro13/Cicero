"""In-memory ``DocumentRepository`` / ``UnitOfWork`` doubles for unit tests.

Writes buffer in the UoW and flush to a shared store on commit, so uncommitted
work stays invisible to other transactions (the real behaviour, ADR-003).
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.ports.document_repository import DocumentRepository
from pagemaster.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


class InMemoryDocumentRepository(DocumentRepository):
    """Shared ``store`` dict + a per-transaction write buffer (read-your-writes);
    the owning UoW flushes the buffer on commit and discards it on rollback."""

    def __init__(self, store: dict[DocumentId, Document]) -> None:
        self._store = store
        self._pending: dict[DocumentId, Document] = {}
        self._pending_deletes: set[DocumentId] = set()
        self.seen: dict[DocumentId, Document] = {}

    async def save(self, document: Document) -> None:
        self._pending_deletes.discard(document.id)
        self._pending[document.id] = document
        self.seen[document.id] = document

    async def delete(self, document: Document) -> None:
        self._pending.pop(document.id, None)
        self._pending_deletes.add(document.id)

    async def find_by_id(self, document_id: DocumentId) -> Document | None:
        if document_id in self._pending_deletes:
            return None
        document = self._pending.get(document_id) or self._store.get(document_id)
        if document is not None:
            self.seen[document.id] = document
        return document

    async def find_all(self) -> list[Document]:
        visible = {**self._store, **self._pending}
        for document_id in self._pending_deletes:
            visible.pop(document_id, None)
        self.seen.update(visible)
        return list(visible.values())

    def flush(self) -> None:
        self._store.update(self._pending)
        for document_id in self._pending_deletes:
            self._store.pop(document_id, None)
        self._pending.clear()
        self._pending_deletes.clear()

    def discard(self) -> None:
        self._pending.clear()
        self._pending_deletes.clear()


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
