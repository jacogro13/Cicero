"""Extract a document → Markdown (ADR-009).

``ExtractDocument`` drives the status machine for real: it commits ``PROCESSING``,
runs extraction, stores the Markdown blob, then commits ``READY`` with a
``content_key`` — or ``FAILED`` if extraction raises. Storage-first mirrors
``UploadDocument`` (ADR-004): a READY document never points at a missing blob.
"""

import pytest

from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.document_status import DocumentStatus
from pagemaster.domain.document.exceptions import DocumentNotFound
from pagemaster.services.document.extract_document import ExtractDocument
from pagemaster.services.document.upload_document import UploadDocument

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    make_in_memory_uow_factory,
)


async def _upload(uow_factory, storage):
    return await UploadDocument(uow_factory, storage).execute(
        title="Clean Code", content=b"%PDF-1.4 source bytes"
    )


class _ExplodingExtractor(StubDocumentExtractor):
    async def extract_markdown(self, data: bytes) -> str:
        raise RuntimeError("extraction failed")


class TestExtractDocument:
    async def test_marks_the_document_ready(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await ExtractDocument(
            uow_factory, storage, StubDocumentExtractor("# Clean Code")
        ).execute(document.id)

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert extracted.status is DocumentStatus.READY

    async def test_stores_the_extracted_markdown_at_the_content_key(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await ExtractDocument(
            uow_factory, storage, StubDocumentExtractor("# Clean Code\n\nBody.")
        ).execute(document.id)

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert await storage.get(extracted.content_key) == b"# Clean Code\n\nBody."

    async def test_commits_processing_before_extraction_runs(self):
        # A spy extractor reads the persisted status mid-extraction: it must
        # already be PROCESSING, i.e. committed before the heavy work begins.
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

        await ExtractDocument(uow_factory, storage, _StatusSpyExtractor()).execute(
            document.id
        )

        assert seen == [DocumentStatus.PROCESSING]

    async def test_extraction_failure_marks_failed_and_stores_no_content(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _upload(uow_factory, storage)

        await ExtractDocument(uow_factory, storage, _ExplodingExtractor()).execute(
            document.id
        )

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert extracted.status is DocumentStatus.FAILED
        # Only the source blob exists — no orphaned content was written.
        assert list(storage.objects) == [document.source_key]

    async def test_unknown_id_raises_document_not_found(self):
        extract = ExtractDocument(
            make_in_memory_uow_factory(),
            InMemoryDocumentStorage(),
            StubDocumentExtractor("# md"),
        )

        with pytest.raises(DocumentNotFound):
            await extract.execute(DocumentId.new())
