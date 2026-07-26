"""Extract a document → chapters — the ``ExtractDocument`` command handler (ADR-009/021).

Drives EXTRACTING→EXTRACTED/FAILED with a stub extractor; stores each chapter's Markdown
at its chapter key and the ordered titles via ``uow.chapters``. Storage-first, so an
EXTRACTED document never points at a missing blob. An unknown id raises ``DocumentNotFound``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.chapter import Chapter
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services.document.extract_document import ExtractDocument

from tests.fakes import (
    InMemoryDocumentStorage,
    StubArticleExtractor,
    StubDocumentExtractor,
    make_in_memory_uow_factory,
)

_CHAPTERS = [Chapter("One", "# One\n\nAaa."), Chapter("Two", "# Two\n\nBbb.")]


async def _uploaded_document(uow_factory, storage):
    """Arrange ExtractDocument's precondition — an UPLOADED document with its source
    blob in storage — built directly rather than via UploadDocument, so this suite
    exercises only the extract handler."""
    document = Document.create("Clean Code")
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.commit()
    await storage.put(document.source_key, b"%PDF-1.4 source bytes")
    return document


async def _extract(uow_factory, storage, extractor, document_id, article_extractor=None):
    command = commands.ExtractDocument(document_id=document_id)
    article_extractor = article_extractor or StubArticleExtractor()
    await ExtractDocument(storage, extractor, article_extractor)(command, uow_factory())


class _ExplodingExtractor(StubDocumentExtractor):
    async def extract(self, data: bytes) -> list[Chapter]:
        raise RuntimeError("extraction failed")


class _DeletingExtractor(StubDocumentExtractor):
    """Simulates a concurrent DELETE landing while extraction runs — the document is
    gone by the time the stage tries to write its result."""

    def __init__(self, uow_factory, document_id, chapters: list[Chapter]) -> None:
        super().__init__(chapters)
        self._uow_factory = uow_factory
        self._document_id = document_id

    async def extract(self, data: bytes) -> list[Chapter]:
        async with self._uow_factory() as uow:
            document = await uow.documents.find_by_id(self._document_id)
            await uow.documents.delete(document)
            await uow.commit()
        return self._chapters


class TestExtractDocument:
    async def test_marks_the_document_extracted(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _uploaded_document(uow_factory, storage)

        await _extract(uow_factory, storage, StubDocumentExtractor(_CHAPTERS), document.id)

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert extracted.status is DocumentStatus.EXTRACTED

    async def test_stores_each_chapter_markdown_at_its_chapter_key(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _uploaded_document(uow_factory, storage)

        await _extract(uow_factory, storage, StubDocumentExtractor(_CHAPTERS), document.id)

        assert await storage.get(document.chapter_key(0)) == b"# One\n\nAaa."
        assert await storage.get(document.chapter_key(1)) == b"# Two\n\nBbb."

    async def test_persists_the_ordered_chapter_titles(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _uploaded_document(uow_factory, storage)

        await _extract(uow_factory, storage, StubDocumentExtractor(_CHAPTERS), document.id)

        async with uow_factory() as uow:
            titles = await uow.chapters.list(document.id)
        assert titles == ["One", "Two"]

    async def test_commits_extracting_before_extraction_runs(self):
        # A spy extractor reads the persisted status mid-extraction: it must already
        # be EXTRACTING, i.e. committed before the heavy work begins.
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _uploaded_document(uow_factory, storage)
        seen: list[DocumentStatus] = []

        class _StatusSpyExtractor(StubDocumentExtractor):
            async def extract(self, data: bytes) -> list[Chapter]:
                async with uow_factory() as uow:
                    mid = await uow.documents.find_by_id(document.id)
                    seen.append(mid.status)
                return _CHAPTERS

        await _extract(uow_factory, storage, _StatusSpyExtractor(), document.id)

        assert seen == [DocumentStatus.EXTRACTING]

    async def test_extraction_failure_marks_failed_and_stores_no_content(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _uploaded_document(uow_factory, storage)

        await _extract(uow_factory, storage, _ExplodingExtractor(), document.id)

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
        assert extracted.status is DocumentStatus.FAILED
        # Only the source blob exists — no orphaned chapter content was written.
        assert list(storage.objects) == [document.source_key]

    async def test_delete_during_extraction_drops_cleanly(self):
        # Deleted mid-flight is not an error (ADR-014): the stage must not crash, must
        # not resurrect the document as EXTRACTED, and must write no orphan chapter blobs.
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _uploaded_document(uow_factory, storage)
        extractor = _DeletingExtractor(uow_factory, document.id, _CHAPTERS)

        await _extract(uow_factory, storage, extractor, document.id)

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None
        assert list(storage.objects) == [document.source_key]

    async def test_unknown_id_raises_document_not_found(self):
        extract = ExtractDocument(
            InMemoryDocumentStorage(), StubDocumentExtractor(), StubArticleExtractor()
        )

        with pytest.raises(DocumentNotFound):
            await extract(
                commands.ExtractDocument(document_id=DocumentId.new()),
                make_in_memory_uow_factory()(),
            )


class TestExtractUrlDocument:
    """A URL-sourced document is fetched and parsed by the ArticleExtractor into a
    single chapter — no source blob is read (ADR-027). The branch is on source_url,
    never on kind (ADR-026)."""

    async def _url_document(self, uow_factory):
        document = Document.create_from_url("https://example.com/blog/clean-architecture")
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()
        return document

    async def test_extracts_the_article_as_a_single_chapter(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await self._url_document(uow_factory)
        article = StubArticleExtractor(Chapter("Clean Architecture", "# Clean Architecture\n\nBody."))

        await _extract(uow_factory, storage, StubDocumentExtractor(), document.id, article)

        async with uow_factory() as uow:
            extracted = await uow.documents.find_by_id(document.id)
            titles = await uow.chapters.list(document.id)
        assert extracted.status is DocumentStatus.EXTRACTED
        assert titles == ["Clean Architecture"]
        assert await storage.get(document.chapter_key(0)) == b"# Clean Architecture\n\nBody."

    async def test_does_not_read_a_source_blob(self):
        # A URL document has no source blob; extraction must not touch storage.get
        # on a missing key. The article extractor is the only source.
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await self._url_document(uow_factory)

        await _extract(uow_factory, storage, StubDocumentExtractor(), document.id)

        # Only the extracted chapter blob exists — no source_key was ever written or read.
        assert list(storage.objects) == [document.chapter_key(0)]
