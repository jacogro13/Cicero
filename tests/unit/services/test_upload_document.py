"""Upload a document → it's stored, driven through the bus (ADR-004, ADR-011).

Storage goes first, so a failed upload can orphan a blob but never persist a document.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.services.document.upload_document import UploadDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import InMemoryDocumentStorage, make_in_memory_uow_factory


class _ExplodingStorage(InMemoryDocumentStorage):
    async def put(self, key: str, data: bytes) -> None:
        raise RuntimeError("object storage is down")


def _bus(uow_factory, storage) -> MessageBus:
    return MessageBus(
        uow_factory,
        command_handlers={commands.UploadDocument: UploadDocument(storage)},
        event_handlers={},
    )


class TestUploadDocument:
    async def test_stores_the_file_under_the_documents_source_key(self):
        storage = InMemoryDocumentStorage()
        bus = _bus(make_in_memory_uow_factory(), storage)

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )

        assert await storage.get(document.source_key) == b"%PDF-1.4 bytes"

    async def test_persists_the_document_so_it_is_fetchable_later(self):
        uow_factory = make_in_memory_uow_factory()
        bus = _bus(uow_factory, InMemoryDocumentStorage())

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )

        async with uow_factory() as uow:
            fetched = await uow.documents.find_by_id(document.id)
        assert fetched == document

    async def test_defaults_to_a_book(self):
        bus = _bus(make_in_memory_uow_factory(), InMemoryDocumentStorage())

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )

        assert document.kind is DocumentKind.BOOK

    async def test_an_explicit_kind_overrides_the_book_default(self):
        # A PDF is a BOOK by default, but the caller may mark it an ARTICLE (ADR-026).
        bus = _bus(make_in_memory_uow_factory(), InMemoryDocumentStorage())

        document = await bus.handle(
            commands.UploadDocument(
                title="A Paper", content=b"%PDF-1.4 bytes", kind=DocumentKind.ARTICLE
            )
        )

        assert document.kind is DocumentKind.ARTICLE

    async def test_uploaded_document_starts_in_uploaded_status(self):
        bus = _bus(make_in_memory_uow_factory(), InMemoryDocumentStorage())

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )

        assert document.status is DocumentStatus.UPLOADED

    async def test_a_storage_failure_persists_no_document(self):
        store = {}
        bus = _bus(make_in_memory_uow_factory(store), _ExplodingStorage())

        with pytest.raises(RuntimeError):
            await bus.handle(
                commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
            )

        assert store == {}
