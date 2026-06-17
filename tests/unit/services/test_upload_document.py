"""Upload a document → it's stored (backlog #4, ADR-004).

The ``UploadDocument`` use case has two effects that must be coordinated: it
puts the source file in object storage and persists the document metadata in a
Unit of Work. Storage comes first, so a failure mid-upload can leave at worst an
orphaned blob, never a committed document whose file is missing. Exercised here
against the in-memory fakes; Batch #7/#8 re-run the behaviour against real
Postgres and object storage.
"""

import pytest

from pagemaster.domain.document.document_status import DocumentStatus
from pagemaster.services.document.upload_document import UploadDocument

from tests.fakes import make_in_memory_uow_factory
from tests.fakes.storage import InMemoryDocumentStorage


class _ExplodingStorage(InMemoryDocumentStorage):
    async def put(self, key: str, data: bytes) -> None:
        raise RuntimeError("object storage is down")


class TestUploadDocument:
    async def test_stores_the_file_under_the_documents_source_key(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        upload = UploadDocument(uow_factory, storage)

        document = await upload.execute(title="Clean Code", content=b"%PDF-1.4 bytes")

        assert await storage.get(document.source_key) == b"%PDF-1.4 bytes"

    async def test_persists_the_document_so_it_is_fetchable_later(self):
        uow_factory = make_in_memory_uow_factory()
        upload = UploadDocument(uow_factory, InMemoryDocumentStorage())

        document = await upload.execute(title="Clean Code", content=b"%PDF-1.4 bytes")

        async with uow_factory() as uow:
            fetched = await uow.documents.find_by_id(document.id)
        assert fetched == document

    async def test_uploaded_document_starts_in_uploaded_status(self):
        upload = UploadDocument(make_in_memory_uow_factory(), InMemoryDocumentStorage())

        document = await upload.execute(title="Clean Code", content=b"%PDF-1.4 bytes")

        assert document.status is DocumentStatus.UPLOADED

    async def test_a_storage_failure_persists_no_document(self):
        store = {}
        uow_factory = make_in_memory_uow_factory(store)
        upload = UploadDocument(uow_factory, _ExplodingStorage())

        with pytest.raises(RuntimeError):
            await upload.execute(title="Clean Code", content=b"%PDF-1.4 bytes")

        assert store == {}
