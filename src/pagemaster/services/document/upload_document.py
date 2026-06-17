from pagemaster.domain.document.document import Document
from pagemaster.domain.document.ports.document_storage import DocumentStorage
from pagemaster.domain.ports.unit_of_work import UnitOfWorkFactory


class UploadDocument:
    """Use case: store a document's source file, then persist its metadata (ADR-004).

    Storage is not transactional with the database, so order matters: the file
    is written before the metadata is committed, leaving at worst an orphaned
    blob — never a document whose file is missing — if the upload fails.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: DocumentStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, title: str, content: bytes) -> Document:
        document = Document.create(title)
        await self._storage.put(document.source_key, content)
        async with self._uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()
        return document
