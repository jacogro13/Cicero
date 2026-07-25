from cicero.domain.document import commands
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork


class DeleteDocument:
    """Handler: remove the metadata and its read-model projections, then the source
    blob — metadata-first (ADR-004, ADR-008).

    Tears down the chapter-title and summary projections in the same transaction, so
    a deleted document leaves no orphan read-model rows (ADR-015/016/021).
    Raises ``DocumentNotFound`` for an unknown id.
    """

    def __init__(self, storage: DocumentStorage) -> None:
        self._storage = storage

    async def __call__(self, command: commands.DeleteDocument, uow: UnitOfWork) -> None:
        document_id = command.document_id
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            storage_prefix = document.storage_prefix
            await uow.documents.delete(document)
            await uow.chapters.delete(document_id)
            await uow.summaries.delete(document_id)
            await uow.commit()
        # Sweep the whole prefix: source blob plus every chapter blob, including any
        # orphan a mid-flight extraction may have written before it was dropped.
        await self._storage.delete_prefix(storage_prefix)
