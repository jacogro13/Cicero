"""The repository port's own behavior (ADR-011): every aggregate passing
through an accessor is registered in ``seen`` by the port itself, so no
implementation can silently skip the bookkeeping the event flow depends on."""

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.document_repository import DocumentRepository


class DictDocumentRepository(DocumentRepository):
    """Pure persistence hooks over a dict — no ``seen`` lines of its own."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[DocumentId, Document] = {}

    async def _save(self, document: Document) -> None:
        self.rows[document.id] = document

    async def _find_by_id(self, document_id: DocumentId) -> Document | None:
        return self.rows.get(document_id)

    async def _find_all(self) -> list[Document]:
        return list(self.rows.values())

    async def _delete(self, document: Document) -> None:
        del self.rows[document.id]


def _stored_repo(*documents: Document) -> DictDocumentRepository:
    repo = DictDocumentRepository()
    repo.rows = {document.id: document for document in documents}
    return repo


class TestSeenTracking:
    async def test_save_marks_the_document_seen(self):
        repo = DictDocumentRepository()
        document = Document.create("Any Title")

        await repo.save(document)

        assert repo.seen == {document.id: document}

    async def test_find_by_id_marks_the_document_seen(self):
        document = Document.create("Any Title")
        repo = _stored_repo(document)

        await repo.find_by_id(document.id)

        assert repo.seen == {document.id: document}

    async def test_missing_id_marks_nothing_seen(self):
        repo = DictDocumentRepository()

        assert await repo.find_by_id(Document.create("Elsewhere").id) is None
        assert repo.seen == {}

    async def test_find_all_marks_every_document_seen(self):
        first = Document.create("First")
        second = Document.create("Second")
        repo = _stored_repo(first, second)

        await repo.find_all()

        assert repo.seen == {first.id: first, second.id: second}

    async def test_delete_marks_the_document_seen(self):
        document = Document.create("Any Title")
        repo = _stored_repo(document)

        await repo.delete(document)

        assert repo.seen == {document.id: document}
