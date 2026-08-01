"""Save & fetch a Document through the repository + Unit of Work.

A committed document is visible to a later transaction; any exit without a
commit — a forgotten commit or an exception mid-block — discards the writes.
"""

import pytest

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentUploaded

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

    async def test_collect_new_events_drains_events_off_seen_aggregates(self):
        uow_factory = make_in_memory_uow_factory()
        doc = Document.create("Domain-Driven Design")

        async with uow_factory() as uow:
            await uow.documents.save(doc)
            events = list(uow.collect_new_events())

        assert events == [DocumentUploaded(document_id=doc.id)]

    async def test_events_are_collected_only_once(self):
        uow_factory = make_in_memory_uow_factory()

        async with uow_factory() as uow:
            await uow.documents.save(Document.create("Refactoring"))
            first = list(uow.collect_new_events())
            second = list(uow.collect_new_events())

        assert len(first) == 1
        assert second == []

    async def test_a_reused_uow_sees_nothing_from_its_earlier_transaction(self):
        # The real UoW builds its repositories in __aenter__, one set per block, so
        # `seen` cannot outlive a transaction. A handler entering the same UoW twice
        # (every pipeline stage does) must not re-drain the first block's aggregates.
        uow_factory = make_in_memory_uow_factory()
        uow = uow_factory()

        async with uow:
            await uow.documents.save(Document.create("Domain-Driven Design"))
            await uow.commit()

        async with uow:
            second = Document.create("Refactoring")
            await uow.documents.save(second)
            events = list(uow.collect_new_events())

        assert events == [DocumentUploaded(document_id=second.id)]

    async def test_an_exception_in_the_block_discards_the_writes(self):
        uow_factory = make_in_memory_uow_factory()
        doc = Document.create("Patterns of Enterprise Application Architecture")

        with pytest.raises(RuntimeError):
            async with uow_factory() as uow:
                await uow.documents.save(doc)
                raise RuntimeError("boom")  # before commit

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(doc.id) is None
