"""The composition root wires the enrichment branch alongside the spine (ADR-028).

Over the in-memory fakes: ``ExtractionCompleted`` — where both source and text
exist — now fans out to *two* queues (a second subscriber feeds the branch), and the
``EnrichDocument`` command reaches its handler. Verified behaviourally, so a rename or
a dropped registration fails here rather than only in the live app.
"""

from __future__ import annotations

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.domain.document.events import ExtractionCompleted
from cicero.entrypoints.dependencies import bootstrap
from cicero.entrypoints.job_queue import JobQueue

from tests.fakes import (
    InMemoryDocumentStorage,
    StubArticleCoverRenderer,
    StubArticleExtractor,
    StubCoverRenderer,
    StubDocumentExtractor,
    StubDocumentSummarizer,
    StubMetadataInferer,
    make_in_memory_uow_factory,
)


def _bus(uow_factory, storage, spine_queue, enrich_queue, *, cover=None):
    return bootstrap(
        uow_factory,
        storage,
        StubDocumentExtractor("# Clean Code"),
        StubArticleExtractor(),
        StubDocumentSummarizer("A summary."),
        cover or StubCoverRenderer(),
        StubArticleCoverRenderer(),
        StubMetadataInferer(),
        spine_queue,
        enrich_queue,
    )


class TestBootstrapWiring:
    async def test_extraction_completed_fans_out_to_both_queues(self):
        uow_factory = make_in_memory_uow_factory()
        spine_queue, enrich_queue = JobQueue(), JobQueue()
        bus = _bus(uow_factory, InMemoryDocumentStorage(), spine_queue, enrich_queue)

        spine, enrich = [], []
        await spine_queue.start(lambda i: _append(spine, i))
        await enrich_queue.start(lambda i: _append(enrich, i))

        document_id = DocumentId.new()
        await bus.handle(ExtractionCompleted(document_id=document_id))
        await spine_queue.join()
        await enrich_queue.join()
        await spine_queue.stop()
        await enrich_queue.stop()

        # One event, two branches: the spine advances to summarization, the branch enriches.
        assert spine == [document_id]
        assert enrich == [document_id]

    async def test_a_retried_document_is_re_enqueued_onto_the_spine(self):
        # The composition root is where a retry becomes work again: without this
        # subscription the status reset would be a dead end (ADR-030).
        uow_factory = make_in_memory_uow_factory()
        document = Document.create("Clean Code")
        document.mark_failed()
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()
        spine_queue, enrich_queue = JobQueue(), JobQueue()
        bus = _bus(uow_factory, InMemoryDocumentStorage(), spine_queue, enrich_queue)

        spine: list[DocumentId] = []
        await spine_queue.start(lambda i: _append(spine, i))
        await bus.handle(commands.RetryDocument(document_id=document.id))
        await spine_queue.join()
        await spine_queue.stop()

        assert spine == [document.id]

    async def test_enrich_document_command_reaches_its_handler(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = Document.create("Clean Code")
        document.mark_extracted()
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.chapters.save(document.id, ["Chapter One"])
            await uow.commit()
        storage.objects[document.source_key] = b"%PDF-fake"
        storage.objects[document.chapter_key(0)] = b"# Clean Code"
        bus = _bus(uow_factory, storage, JobQueue(), JobQueue(), cover=StubCoverRenderer())

        await bus.handle(commands.EnrichDocument(document_id=document.id))

        async with uow_factory() as uow:
            enriched = await uow.documents.find_by_id(document.id)
        assert enriched.enrichment_status is EnrichmentStatus.ENRICHED
        assert enriched.has_cover is True


async def _append(sink: list, value) -> None:
    sink.append(value)
