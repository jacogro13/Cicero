"""List documents, now a command handler (ADR-011, ADR-012).

``ListDocuments`` returns every committed document. It is a read — no deps, no
commit — but rides the bus like the others; the bus supplies the UoW per call.
"""

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.services.document.list_documents import ListDocuments

from tests.fakes import make_in_memory_uow_factory


async def _list(uow_factory):
    return await ListDocuments()(commands.ListDocuments(), uow_factory())


class TestListDocuments:
    async def test_returns_all_committed_documents(self):
        uow_factory = make_in_memory_uow_factory()
        first = Document.create("Clean Code")
        second = Document.create("Refactoring")
        async with uow_factory() as uow:
            await uow.documents.save(first)
            await uow.documents.save(second)
            await uow.commit()

        documents = await _list(uow_factory)

        assert len(documents) == 2
        assert {d.id for d in documents} == {first.id, second.id}

    async def test_returns_an_empty_list_when_there_are_no_documents(self):
        assert await _list(make_in_memory_uow_factory()) == []
