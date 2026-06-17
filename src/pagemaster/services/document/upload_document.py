from pagemaster.domain.document.document import Document
from pagemaster.domain.document.ports.document_storage import DocumentStorage
from pagemaster.domain.ports.unit_of_work import UnitOfWorkFactory


class UploadDocument:
    """Use case: upload a document → it's stored (ADR-004).

    Stores the source file in object storage, then persists the document
    metadata in a Unit of Work. Storage comes first: object storage is not
    transactional with the database, and an orphaned blob is harmless and
    garbage-collectable, whereas a committed document whose file is missing is a
    user-visible failure. So if the upload fails, no document is persisted.

    Dependencies are constructor parameters (ADR-001/003): a ``uow_factory`` and
    a :class:`DocumentStorage`, never globals.
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
