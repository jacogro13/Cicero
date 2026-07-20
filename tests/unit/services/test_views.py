"""The read side: list documents as read-shaped DTOs, bypassing the bus (ADR-015)."""

from cicero.domain.document.document import Document
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
