"""Read-model teardown against real Postgres (ADR-016/021, ADR-023).

Deleting a document drops its chapter-title and summary projections
(``uow.chapters.delete`` / ``uow.summaries.delete``). Verified over the wire like
the repository contract: the delete must remove the targeted document's rows and
only those, and be a no-op when there are none.
"""

from cicero.domain.document.document_id import DocumentId
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory


class TestChapterReadModelDeletionOnPostgres:
    async def test_delete_removes_only_the_targeted_documents_titles(
        self, uow_factory: UnitOfWorkFactory
    ):
        keep, drop = DocumentId.new(), DocumentId.new()
        async with uow_factory() as uow:
            await uow.chapters.save(keep, ["K1", "K2"])
            await uow.chapters.save(drop, ["D1", "D2"])
            await uow.commit()

        async with uow_factory() as uow:
            await uow.chapters.delete(drop)
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.chapters.list(drop) == []
            assert await uow.chapters.list(keep) == ["K1", "K2"]

    async def test_delete_is_a_no_op_for_a_document_with_no_chapters(
        self, uow_factory: UnitOfWorkFactory
    ):
        async with uow_factory() as uow:
            await uow.chapters.delete(DocumentId.new())
            await uow.commit()


class TestSummaryReadModelDeletionOnPostgres:
    async def test_delete_removes_only_the_targeted_documents_summaries(
        self, uow_factory: UnitOfWorkFactory
    ):
        keep, drop = DocumentId.new(), DocumentId.new()
        async with uow_factory() as uow:
            await uow.summaries.save(keep, 0, "keep 0")
            await uow.summaries.save(drop, 0, "drop 0")
            await uow.summaries.save(drop, 1, "drop 1")
            await uow.commit()

        async with uow_factory() as uow:
            await uow.summaries.delete(drop)
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.summaries.all(drop) == {}
            assert await uow.summaries.all(keep) == {0: "keep 0"}

    async def test_delete_is_a_no_op_for_a_document_with_no_summaries(
        self, uow_factory: UnitOfWorkFactory
    ):
        async with uow_factory() as uow:
            await uow.summaries.delete(DocumentId.new())
            await uow.commit()
