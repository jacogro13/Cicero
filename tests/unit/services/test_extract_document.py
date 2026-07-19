"""Extract a document → Markdown — the ``ExtractDocument`` command handler (ADR-009/013).

Drives EXTRACTING→EXTRACTED/FAILED with a stub extractor; storage-first, so an EXTRACTED
document never points at a missing blob. An unknown id raises ``DocumentNotFound``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.upload_document import UploadDocument

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    make_in_memory_uow_factory,
)


async def _upload(uow_factory, storage):
    command = commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 source bytes")
    return await UploadDocument(storage)(command, uow_factory())


async def _extract(uow_factory, storage, extractor, document_id):
    command = commands.ExtractDocument(document_id=document_id)
    await ExtractDocument(storage, extractor)(command, uow_factory())


class _ExplodingExtractor(StubDocumentExtractor):
    async def extract_markdown(self, data: bytes) -> str:
        raise RuntimeError("extraction failed")


class TestExtractDocument:
    async def test_marks_the_document_extracted(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await _extract(
            uow_factory, storage, StubDocumentExtractor("# Clean Code"), document.id
        )

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert extracted.status is DocumentStatus.EXTRACTED

    async def test_stores_the_extracted_markdown_at_the_content_key(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await _extract(
            uow_factory, storage, StubDocumentExtractor("# Clean Code\n\nBody."), document.id
        )

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert await storage.get(extracted.content_key) == b"# Clean Code\n\nBody."

    async def test_commits_extracting_before_extraction_runs(self):
        # A spy extractor reads the persisted status mid-extraction: it must
        # already be EXTRACTING, i.e. committed before the heavy work begins.
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)
        seen: list[DocumentStatus] = []

        class _StatusSpyExtractor(StubDocumentExtractor):
            async def extract_markdown(self, data: bytes) -> str:
                async with uow_factory() as uow:
                    mid = await uow.documents.find_by_id(document.id)
                    seen.append(mid.status)
                return "# md"

        await _extract(uow_factory, storage, _StatusSpyExtractor(), document.id)

        assert seen == [DocumentStatus.EXTRACTING]

    async def test_extraction_failure_marks_failed_and_stores_no_content(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await _extract(uow_factory, storage, _ExplodingExtractor(), document.id)

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert extracted.status is DocumentStatus.FAILED
        # Only the source blob exists — no orphaned content was written.
        assert list(storage.objects) == [document.source_key]

    async def test_unknown_id_raises_document_not_found(self):
        extract = ExtractDocument(InMemoryDocumentStorage(), StubDocumentExtractor("# md"))

        with pytest.raises(DocumentNotFound):
            await extract(
                commands.ExtractDocument(document_id=DocumentId.new()),
                make_in_memory_uow_factory()(),
            )
