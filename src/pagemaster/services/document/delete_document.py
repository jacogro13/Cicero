from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.exceptions import DocumentNotFound
from pagemaster.domain.document.ports.document_storage import DocumentStorage
from pagemaster.domain.ports.unit_of_work import UnitOfWorkFactory


class DeleteDocument:
    """Use case: remove a document and its source file.

    Metadata first, then the blob — the mirror of ``UploadDocument``'s ordering
    (ADR-004): the safe failure mode is an orphaned blob, never a metadata row
    pointing at a missing file. Raises ``DocumentNotFound`` for an unknown id.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, storage: DocumentStorage) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, document_id: DocumentId) -> None:
        async with self._uow_factory() as uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            source_key = document.source_key
            await uow.documents.delete(document)
            await uow.commit()
        await self._storage.delete(source_key)
