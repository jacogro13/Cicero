"""Delete a document — a command handler (ADR-008).

Removes the metadata then the source blob (ADR-004 ordering); an unknown id raises
``DocumentNotFound`` — the domain signals it, HTTP is mapped elsewhere.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services.document.delete_document import DeleteDocument

from tests.fakes import InMemoryDocumentStorage, make_in_memory_uow_factory


async def _stored_document(uow_factory, storage):
    """Arrange DeleteDocument's precondition — a persisted document with its source
    blob in storage — built directly rather than via UploadDocument, so this suite
    exercises only the delete handler."""
    document = Document.create("Clean Code")
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.commit()
    await storage.put(document.source_key, b"%PDF-1.4 bytes")
    return document


async def _delete(uow_factory, storage, document_id):
    await DeleteDocument(storage)(
        commands.DeleteDocument(document_id=document_id), uow_factory()
    )


class TestDeleteDocument:
    async def test_deleted_document_is_no_longer_persisted(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _stored_document(uow_factory, storage)

        await _delete(uow_factory, storage, document.id)

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None

    async def test_deletes_the_source_file_from_storage(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _stored_document(uow_factory, storage)

        await _delete(uow_factory, storage, document.id)

        assert document.source_key not in storage.objects

    async def test_deletes_the_chapter_and_summary_projections(self):
        # A deleted document leaves no orphan read-model rows behind (ADR-015/016/021).
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _stored_document(uow_factory, storage)
        async with uow_factory() as uow:
            await uow.chapters.save(document.id, ["Intro", "Body"])
            await uow.summaries.save(document.id, 0, "Intro summary")
            await uow.summaries.save(document.id, 1, "Body summary")
            await uow.commit()

        await _delete(uow_factory, storage, document.id)

        async with uow_factory() as uow:
            assert await uow.chapters.list(document.id) == []
            assert await uow.summaries.all(document.id) == {}

    async def test_deletes_every_blob_of_the_document_including_chapters(self):
        # Not just the source: chapter Markdown blobs (and any orphan from a mid-flight
        # extraction) share the document's storage prefix and go with it (ADR-004).
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _stored_document(uow_factory, storage)
        await storage.put(document.chapter_key(0), b"# Intro")
        await storage.put(document.chapter_key(1), b"# Body")

        await _delete(uow_factory, storage, document.id)

        assert storage.objects == {}

    async def test_unknown_id_raises_document_not_found(self):
        with pytest.raises(DocumentNotFound):
            await _delete(make_in_memory_uow_factory(), InMemoryDocumentStorage(), DocumentId.new())
