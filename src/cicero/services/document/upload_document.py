from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork


class UploadDocument:
    """Handler: store a document's source file, then persist its metadata (ADR-004, ADR-011).

    Storage is not transactional with the database, so order matters: the file
    is written before the metadata is committed, leaving at worst an orphaned
    blob — never a document whose file is missing — if the upload fails. Storage
    is injected at bootstrap; the bus supplies the Unit of Work per call.
    """

    def __init__(self, storage: DocumentStorage) -> None:
        self._storage = storage

    async def __call__(self, command: commands.UploadDocument, uow: UnitOfWork) -> Document:
        document = Document.create(command.title)
        await self._storage.put(document.source_key, command.content)
        async with uow:
            await uow.documents.save(document)
            await uow.commit()
        return document
