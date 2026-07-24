"""In-memory ``DocumentRepository`` / ``UnitOfWork`` doubles for unit tests.

Writes buffer in the UoW and flush to a shared store on commit, so uncommitted
work stays invisible to other transactions (the real behaviour, ADR-003).
"""

from __future__ import annotations

from dataclasses import replace
from types import TracebackType
from typing import Self

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.chapter_read_model import ChapterReadModel
from cicero.domain.document.ports.document_repository import DocumentRepository
from cicero.domain.document.ports.summary_read_model import SummaryReadModel
from cicero.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


class InMemoryDocumentRepository(DocumentRepository):
    """Shared ``store`` dict + a per-transaction write buffer (read-your-writes);
    the owning UoW flushes the buffer on commit and discards it on rollback."""

    def __init__(self, store: dict[DocumentId, Document]) -> None:
        super().__init__()
        self._store = store
        self._pending: dict[DocumentId, Document] = {}
        self._pending_deletes: set[DocumentId] = set()

    async def _save(self, document: Document) -> None:
        self._pending_deletes.discard(document.id)
        self._pending[document.id] = document

    async def _delete(self, document: Document) -> None:
        self._pending.pop(document.id, None)
        self._pending_deletes.add(document.id)

    async def _find_by_id(self, document_id: DocumentId) -> Document | None:
        if document_id in self._pending_deletes:
            return None
        return self._pending.get(document_id) or self._store.get(document_id)

    async def _find_all(self) -> list[Document]:
        visible = {**self._store, **self._pending}
        for document_id in self._pending_deletes:
            visible.pop(document_id, None)
        return list(visible.values())

    def flush(self) -> None:
        # Store a detached copy, mirroring the Postgres adapter expunging on commit:
        # a returned aggregate is then insulated from a later transaction's writes,
        # and committed state carries no pending events to be drained twice.
        for document_id, document in self._pending.items():
            self._store[document_id] = replace(document)
        for document_id in self._pending_deletes:
            self._store.pop(document_id, None)
        self._pending.clear()
        self._pending_deletes.clear()

    def discard(self) -> None:
        self._pending.clear()
        self._pending_deletes.clear()


class InMemorySummaryReadModel(SummaryReadModel):
    """Shared per-chapter summaries dict (keyed by document id + chapter index) + a
    per-transaction write buffer, mirroring the repository's commit/rollback so a
    summary is visible only once committed."""

    def __init__(self, store: dict[tuple[DocumentId, int], str]) -> None:
        self._store = store
        self._pending: dict[tuple[DocumentId, int], str] = {}

    async def save(self, document_id: DocumentId, chapter_index: int, text: str) -> None:
        self._pending[(document_id, chapter_index)] = text

    async def get(self, document_id: DocumentId, chapter_index: int) -> str | None:
        key = (document_id, chapter_index)
        if key in self._pending:
            return self._pending[key]
        return self._store.get(key)

    async def all(self, document_id: DocumentId) -> dict[int, str]:
        merged = {**self._store, **self._pending}
        return {index: text for (owner, index), text in merged.items() if owner == document_id}

    def flush(self) -> None:
        self._store.update(self._pending)
        self._pending.clear()

    def discard(self) -> None:
        self._pending.clear()


class InMemoryChapterReadModel(ChapterReadModel):
    """Shared chapters dict + a per-transaction write buffer, mirroring the
    repository's commit/rollback so titles are visible only once committed."""

    def __init__(self, store: dict[DocumentId, list[str]]) -> None:
        self._store = store
        self._pending: dict[DocumentId, list[str]] = {}

    async def save(self, document_id: DocumentId, titles: list[str]) -> None:
        self._pending[document_id] = list(titles)

    async def list(self, document_id: DocumentId) -> list[str]:
        if document_id in self._pending:
            return list(self._pending[document_id])
        return list(self._store.get(document_id, []))

    def flush(self) -> None:
        self._store.update(self._pending)
        self._pending.clear()

    def discard(self) -> None:
        self._pending.clear()


class InMemoryUnitOfWork(UnitOfWork):
    """One ``async with`` block is one transaction over the shared stores."""

    def __init__(
        self,
        store: dict[DocumentId, Document],
        chapter_store: dict[DocumentId, list[str]],
        summary_store: dict[tuple[DocumentId, int], str],
    ) -> None:
        self.documents = InMemoryDocumentRepository(store)
        self.chapters = InMemoryChapterReadModel(chapter_store)
        self.summaries = InMemorySummaryReadModel(summary_store)

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
        # rollback() after a commit() is a no-op (the buffers are already empty).
        await self.rollback()

    async def commit(self) -> None:
        self.documents.flush()
        self.chapters.flush()
        self.summaries.flush()

    async def rollback(self) -> None:
        self.documents.discard()
        self.chapters.discard()
        self.summaries.discard()


def make_in_memory_uow_factory(
    store: dict[DocumentId, Document] | None = None,
) -> UnitOfWorkFactory:
    """Return a zero-arg factory yielding fresh UoWs over shared stores.

    All UoWs from a given factory see the same committed data, so tests can
    write in one transaction and read it back in another.
    """
    backing_store: dict[DocumentId, Document] = {} if store is None else store
    chapter_store: dict[DocumentId, list[str]] = {}
    summary_store: dict[tuple[DocumentId, int], str] = {}

    def factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(backing_store, chapter_store, summary_store)

    return factory
