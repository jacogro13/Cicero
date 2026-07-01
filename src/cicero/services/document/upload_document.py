from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork


class UploadDocument:
    """Handler: store the source file, then commit the metadata — storage-first (ADR-004)."""

    def __init__(self, storage: DocumentStorage) -> None:
        self._storage = storage

    async def __call__(self, command: commands.UploadDocument, uow: UnitOfWork) -> Document:
        document = Document.create(command.title)
        await self._storage.put(document.source_key, command.content)
        async with uow:
            await uow.documents.save(document)
            await uow.commit()
        return document
