"""Save & fetch a Document through the repository + Unit of Work ports.

Backlog #3: a document saved and committed in one transaction can be fetched
by id in a later one; the Unit of Work is the transaction boundary, so writes
that are not committed never become visible — whether the block simply forgot
to commit or raised partway through. Exercised here against the in-memory
fakes; Batch #7 re-runs this contract against real Postgres.
"""

import pytest

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId

from tests.fakes import make_in_memory_uow_factory


class TestSaveAndFetchDocument:
    async def test_committed_document_is_visible_in_a_later_transaction(self):
        uow_factory = make_in_memory_uow_factory()
        doc = Document.create("Domain-Driven Design")

        async with uow_factory() as uow:
            await uow.documents.save(doc)
            await uow.commit()

        async with uow_factory() as uow:
            fetched = await uow.documents.find_by_id(doc.id)

        assert fetched == doc

    async def test_find_by_id_returns_none_for_an_unknown_id(self):
        uow_factory = make_in_memory_uow_factory()

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(DocumentId.new()) is None

    async def test_writes_are_not_persisted_without_a_commit(self):
        uow_factory = make_in_memory_uow_factory()
        doc = Document.create("Refactoring")

        async with uow_factory() as uow:
            await uow.documents.save(doc)
            # no commit — the transaction rolls back on exit

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(doc.id) is None

    async def test_an_exception_in_the_block_discards_the_writes(self):
        uow_factory = make_in_memory_uow_factory()
        doc = Document.create("Patterns of Enterprise Application Architecture")

        with pytest.raises(RuntimeError):
            async with uow_factory() as uow:
                await uow.documents.save(doc)
                raise RuntimeError("boom")  # before commit

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(doc.id) is None
