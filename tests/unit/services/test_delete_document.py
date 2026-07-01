"""Delete a document — a command handler (ADR-008).

Removes the metadata then the source blob (ADR-004 ordering); an unknown id raises
``DocumentNotFound`` — the domain signals it, HTTP is mapped elsewhere.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.upload_document import UploadDocument

from tests.fakes import InMemoryDocumentStorage, make_in_memory_uow_factory


async def _upload(uow_factory, storage):
    command = commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
    return await UploadDocument(storage)(command, uow_factory())


async def _delete(uow_factory, storage, document_id):
    await DeleteDocument(storage)(
        commands.DeleteDocument(document_id=document_id), uow_factory()
    )


class TestDeleteDocument:
    async def test_deleted_document_is_no_longer_persisted(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await _delete(uow_factory, storage, document.id)

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None

    async def test_deletes_the_source_file_from_storage(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await _delete(uow_factory, storage, document.id)

        assert document.source_key not in storage.objects

    async def test_unknown_id_raises_document_not_found(self):
        with pytest.raises(DocumentNotFound):
            await _delete(make_in_memory_uow_factory(), InMemoryDocumentStorage(), DocumentId.new())
