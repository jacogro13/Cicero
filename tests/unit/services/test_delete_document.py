"""Delete a document (ADR-008).

``DeleteDocument`` removes the metadata then the source file — the mirror of
``UploadDocument``'s ordering (ADR-004) — and raises ``DocumentNotFound`` when the
id is unknown, leaving the domain to signal the failure (HTTP is mapped elsewhere).
"""

import pytest

from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.exceptions import DocumentNotFound
from pagemaster.services.document.delete_document import DeleteDocument
from pagemaster.services.document.upload_document import UploadDocument

from tests.fakes import InMemoryDocumentStorage, make_in_memory_uow_factory


async def _upload(uow_factory, storage):
    return await UploadDocument(uow_factory, storage).execute(
        title="Clean Code", content=b"%PDF-1.4 bytes"
    )


class TestDeleteDocument:
    async def test_deleted_document_is_no_longer_persisted(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await DeleteDocument(uow_factory, storage).execute(document.id)

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None

    async def test_deletes_the_source_file_from_storage(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await DeleteDocument(uow_factory, storage).execute(document.id)

        assert document.source_key not in storage.objects

    async def test_unknown_id_raises_document_not_found(self):
        uow_factory = make_in_memory_uow_factory()
        delete = DeleteDocument(uow_factory, InMemoryDocumentStorage())

        with pytest.raises(DocumentNotFound):
            await delete.execute(DocumentId.new())
