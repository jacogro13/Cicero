"""The ADR-003 save/fetch/rollback contract, re-verified against real Postgres.

Same behaviours as the in-memory spec (tests/unit/persistence) — the database is
a swappable adapter behind the same ports, so it must behave identically (ADR-006).
"""

import pytest

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory


class TestDocumentPersistenceOnPostgres:
    async def test_committed_document_is_visible_in_a_later_transaction(
        self, uow_factory: UnitOfWorkFactory
    ):
        doc = Document.create("Domain-Driven Design")

        async with uow_factory() as uow:
            await uow.documents.save(doc)
            await uow.commit()

        async with uow_factory() as uow:
            fetched = await uow.documents.find_by_id(doc.id)

        assert fetched == doc

    async def test_find_by_id_returns_none_for_an_unknown_id(
        self, uow_factory: UnitOfWorkFactory
    ):
        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(DocumentId.new()) is None

    async def test_find_all_returns_every_committed_document(
        self, uow_factory: UnitOfWorkFactory
    ):
        titles = {"Refactoring", "Implementing DDD", "Release It!"}

        async with uow_factory() as uow:
            for title in titles:
                await uow.documents.save(Document.create(title))
            await uow.commit()

        async with uow_factory() as uow:
            stored = await uow.documents.find_all()

        assert {doc.title for doc in stored} == titles

    async def test_writes_are_not_persisted_without_a_commit(
        self, uow_factory: UnitOfWorkFactory
    ):
        doc = Document.create("Refactoring")

        async with uow_factory() as uow:
            await uow.documents.save(doc)
            # no commit — the transaction rolls back on exit

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(doc.id) is None

    async def test_an_exception_in_the_block_discards_the_writes(
        self, uow_factory: UnitOfWorkFactory
    ):
        doc = Document.create("Patterns of Enterprise Application Architecture")

        with pytest.raises(RuntimeError):
            async with uow_factory() as uow:
                await uow.documents.save(doc)
                raise RuntimeError("boom")  # before commit

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(doc.id) is None

    async def test_committed_delete_removes_the_document(
        self, uow_factory: UnitOfWorkFactory
    ):
        doc = Document.create("Working Effectively with Legacy Code")

        async with uow_factory() as uow:
            await uow.documents.save(doc)
            await uow.commit()

        async with uow_factory() as uow:
            await uow.documents.delete(await uow.documents.find_by_id(doc.id))
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(doc.id) is None
