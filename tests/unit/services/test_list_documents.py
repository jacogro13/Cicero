"""List documents.

``ListDocuments`` returns every committed document; it is a read, so it takes
only a ``uow_factory`` (no storage) and opens a single transaction.
"""

from pagemaster.domain.document.document import Document
from pagemaster.services.document.list_documents import ListDocuments

from tests.fakes import make_in_memory_uow_factory


class TestListDocuments:
    async def test_returns_all_committed_documents(self):
        uow_factory = make_in_memory_uow_factory()
        first = Document.create("Clean Code")
        second = Document.create("Refactoring")
        async with uow_factory() as uow:
            await uow.documents.save(first)
            await uow.documents.save(second)
            await uow.commit()

        documents = await ListDocuments(uow_factory).execute()

        assert len(documents) == 2
        assert {d.id for d in documents} == {first.id, second.id}

    async def test_returns_an_empty_list_when_there_are_no_documents(self):
        documents = await ListDocuments(make_in_memory_uow_factory()).execute()

        assert documents == []
