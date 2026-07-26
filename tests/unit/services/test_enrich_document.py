"""Enrich a document → cover + authors + year — the ``EnrichDocument`` handler
(ADR-028).

A best-effort branch off the readability spine: it drives the enrichment status
(PENDING→ENRICHING→ENRICHED/FAILED) and fills the metadata, but never touches
``status`` — a failure leaves the document exactly as readable as before. Built with
stub enrichment ports, from a document already at EXTRACTED with its chapters stored.
"""

from __future__ import annotations

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.domain.document.ports.cover_renderer import RenderedCover
from cicero.domain.document.ports.metadata_inferer import InferredMetadata
from cicero.services.document.enrich_document import EnrichDocument

from tests.fakes import (
    InMemoryDocumentStorage,
    StubArticleCoverRenderer,
    StubCoverRenderer,
    StubMetadataInferer,
    make_in_memory_uow_factory,
)

_OPENING = b"# Clean Code\n\nby Robert C. Martin, 2008"


async def _extracted_pdf(uow_factory, storage):
    document = Document.create("Clean Code")
    document.mark_extracted()
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.chapters.save(document.id, ["Chapter One"])
        await uow.commit()
    storage.objects[document.source_key] = b"%PDF-fake-bytes"
    storage.objects[document.chapter_key(0)] = _OPENING
    return document


async def _extracted_article(uow_factory, storage):
    document = Document.create_from_url("https://example.com/post")
    document.mark_extracted()
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.chapters.save(document.id, ["An Article"])
        await uow.commit()
    storage.objects[document.chapter_key(0)] = _OPENING
    return document


async def _enrich(uow_factory, storage, document_id, *, cover=None, article=None, inferer=None):
    handler = EnrichDocument(
        storage,
        cover or StubCoverRenderer(),
        article or StubArticleCoverRenderer(),
        inferer or StubMetadataInferer(),
    )
    await handler(commands.EnrichDocument(document_id=document_id), uow_factory())


class TestEnrichDocument:
    async def test_pdf_happy_path_stores_the_cover_and_marks_enriched(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)

        await _enrich(
            uow_factory, storage, document.id, cover=StubCoverRenderer(RenderedCover(b"PNG!"))
        )

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.enrichment_status is EnrichmentStatus.ENRICHED
        assert enriched.has_cover is True
        assert storage.objects[document.cover_key] == b"PNG!"
        # The readability spine is untouched — enrichment never gates it.
        assert enriched.status is DocumentStatus.EXTRACTED

    async def test_infers_authors_and_year_from_the_opening_text(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)
        inferer = StubMetadataInferer(InferredMetadata(authors="Robert C. Martin", year=2008))

        await _enrich(uow_factory, storage, document.id, inferer=inferer)

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.authors == "Robert C. Martin"
        assert enriched.year == 2008
        assert inferer.received == _OPENING.decode()

    async def test_docinfo_fills_in_what_the_model_leaves_blank(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)
        cover = StubCoverRenderer(RenderedCover(b"PNG", author="Docinfo Author", year=2001))

        await _enrich(
            uow_factory, storage, document.id, cover=cover, inferer=StubMetadataInferer()
        )

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.authors == "Docinfo Author"
        assert enriched.year == 2001

    async def test_model_metadata_wins_over_docinfo(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)
        cover = StubCoverRenderer(RenderedCover(b"PNG", author="Docinfo Author", year=2001))
        inferer = StubMetadataInferer(InferredMetadata(authors="Model Author", year=1999))

        await _enrich(uow_factory, storage, document.id, cover=cover, inferer=inferer)

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.authors == "Model Author"
        assert enriched.year == 1999

    async def test_article_fetches_the_og_image_cover(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_article(uow_factory, storage)
        article = StubArticleCoverRenderer(cover=b"OG-BYTES")

        await _enrich(uow_factory, storage, document.id, article=article)

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.has_cover is True
        assert storage.objects[document.cover_key] == b"OG-BYTES"
        assert article.received == "https://example.com/post"

    async def test_article_without_an_og_image_is_enriched_without_a_cover(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_article(uow_factory, storage)

        await _enrich(
            uow_factory, storage, document.id, article=StubArticleCoverRenderer(cover=None)
        )

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.enrichment_status is EnrichmentStatus.ENRICHED
        assert enriched.has_cover is False
        assert document.cover_key not in storage.objects

    async def test_commits_enriching_before_the_work_runs(self):
        # A spy inferer reads the persisted status mid-call: it must already be
        # ENRICHING, i.e. committed before the heavy work begins (mirrors summarise).
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)
        seen: list[EnrichmentStatus] = []

        class _StatusSpy(StubMetadataInferer):
            async def infer(self, text):
                async with uow_factory() as uow:
                    mid = await uow.documents.find_by_id(document.id)
                    seen.append(mid.enrichment_status)
                return InferredMetadata()

        await _enrich(uow_factory, storage, document.id, inferer=_StatusSpy())

        assert seen == [EnrichmentStatus.ENRICHING]

    async def test_failure_marks_enrichment_failed_and_leaves_the_spine_readable(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)
        exploding = StubCoverRenderer(error=RuntimeError("render boom"))

        await _enrich(uow_factory, storage, document.id, cover=exploding)

        async with uow_factory() as uow:
            failed = await uow.documents.find_by_id(document.id)
        assert failed.enrichment_status is EnrichmentStatus.FAILED
        assert failed.has_cover is False
        assert document.cover_key not in storage.objects
        # The document is exactly as readable as before — best-effort never gates.
        assert failed.status is DocumentStatus.EXTRACTED

    async def test_delete_mid_enrichment_drops_without_resurrecting(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_pdf(uow_factory, storage)

        class _DeleteDuringInfer(StubMetadataInferer):
            async def infer(self, text):
                async with uow_factory() as uow:
                    await uow.documents.delete(await uow.documents.find_by_id(document.id))
                    await uow.commit()
                return InferredMetadata()

        await _enrich(uow_factory, storage, document.id, inferer=_DeleteDuringInfer())

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None
        assert document.cover_key not in storage.objects

    async def test_unknown_id_is_dropped_without_raising(self):
        uow_factory = make_in_memory_uow_factory()
        # Best-effort: a stale intent for a vanished document is a no-op, never a raise.
        await _enrich(uow_factory, InMemoryDocumentStorage(), Document.create("x").id)
