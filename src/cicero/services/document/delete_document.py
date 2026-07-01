from cicero.domain.document import commands
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork


class DeleteDocument:
    """Handler: remove the metadata, then the source blob — metadata-first (ADR-004, ADR-008).

    Raises ``DocumentNotFound`` for an unknown id.
    """

    def __init__(self, storage: DocumentStorage) -> None:
        self._storage = storage

    async def __call__(self, command: commands.DeleteDocument, uow: UnitOfWork) -> None:
        async with uow:
            document = await uow.documents.find_by_id(command.document_id)
            if document is None:
                raise DocumentNotFound(command.document_id)
            source_key = document.source_key
            await uow.documents.delete(document)
            await uow.commit()
        await self._storage.delete(source_key)
