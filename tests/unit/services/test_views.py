"""The read side: list documents and read a summary, bypassing the bus (ADR-015/016)."""

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.services import views

from tests.fakes import make_in_memory_uow_factory


class TestListDocuments:
    async def test_returns_a_view_per_committed_document(self):
        uow_factory = make_in_memory_uow_factory()
        first = Document.create("Clean Code")
        second = Document.create("Refactoring")
        async with uow_factory() as uow:
            await uow.documents.save(first)
            await uow.documents.save(second)
            await uow.commit()

        documents = await views.list_documents(uow_factory)

        assert {(d.id, d.title, d.status) for d in documents} == {
            (first.id, "Clean Code", DocumentStatus.UPLOADED),
            (second.id, "Refactoring", DocumentStatus.UPLOADED),
        }

    async def test_returns_read_dtos_not_aggregates(self):
        uow_factory = make_in_memory_uow_factory()
        async with uow_factory() as uow:
            await uow.documents.save(Document.create("Clean Code"))
            await uow.commit()

        [view] = await views.list_documents(uow_factory)

        assert isinstance(view, views.DocumentView)
        assert not isinstance(view, Document)

    async def test_returns_an_empty_list_when_there_are_no_documents(self):
        assert await views.list_documents(make_in_memory_uow_factory()) == []


class TestGetDocumentSummary:
    async def test_returns_the_written_summary(self):
        # The summaries read model is written by the summarisation stage; the view
        # reads it directly, never re-deriving from the aggregate (ADR-016).
        uow_factory = make_in_memory_uow_factory()
        document = Document.create("Clean Code")
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.summaries.save(document.id, "A crisp summary.")
            await uow.commit()

        summary = await views.get_document_summary(uow_factory, document.id)

        assert isinstance(summary, views.SummaryView)
        assert summary.text == "A crisp summary."

    async def test_returns_none_when_the_document_has_no_summary(self):
        assert (
            await views.get_document_summary(
                make_in_memory_uow_factory(), DocumentId.new()
            )
            is None
        )
