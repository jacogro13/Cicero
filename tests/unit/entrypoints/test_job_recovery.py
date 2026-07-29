"""Restart recovery: re-enqueue every document the pipeline is not done with (ADR-014).

No longer a special case. Recovery asks the same question ordinary dispatch asks —
"does this status have a next stage?" — so it reconstructs the outstanding work from
persisted status alone, with no jobs table, and picks up the `UPLOADED`-but-never-enqueued
gap ADR-013 left open for free.
"""

from __future__ import annotations

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.job_recovery import (
    reconcile_pending_enrichment,
    reconcile_unfinished_documents,
)

from tests.fakes import make_in_memory_uow_factory


def _document(status: DocumentStatus) -> Document:
    document = Document.create("Clean Code")
    document.status = status
    return document


def _enrichment(status: DocumentStatus, enrichment: EnrichmentStatus) -> Document:
    document = _document(status)
    document.enrichment_status = enrichment
    return document


async def _record(sink: list, value) -> None:
    sink.append(value)


class TestReconcileUnfinishedDocuments:
    async def test_reenqueues_every_document_with_a_next_stage(self):
        # UPLOADED counts too: a crash between the upload commit and the enqueue
        # used to strand the document (ADR-013 consequence), and no longer does.
        # Every status a stage still owes work on is re-enqueued (ADR-014/016).
        unfinished = [
            _document(DocumentStatus.UPLOADED),
            _document(DocumentStatus.EXTRACTING),
            _document(DocumentStatus.EXTRACTED),
            _document(DocumentStatus.SUMMARISING),
        ]
        terminal = [
            _document(DocumentStatus.SUMMARISED),
            _document(DocumentStatus.FAILED),
        ]
        store = {d.id: d for d in unfinished + terminal}
        uow_factory = make_in_memory_uow_factory(store)

        drained: list[DocumentId] = []
        queue = JobQueue()
        await queue.start(lambda document_id: _record(drained, document_id))

        count = await reconcile_unfinished_documents(queue, uow_factory)
        await queue.join()
        await queue.stop()

        assert count == 4
        assert set(drained) == {d.id for d in unfinished}

    async def test_nothing_to_recover_returns_zero(self):
        queue = JobQueue()
        await queue.start(lambda document_id: _record([], document_id))

        count = await reconcile_unfinished_documents(queue, make_in_memory_uow_factory())

        await queue.stop()
        assert count == 0


class TestReconcilePendingEnrichment:
    async def test_reenqueues_text_ready_documents_the_branch_still_owes(self):
        # The enrichment mirror of spine recovery, onto the branch's own queue: a
        # document whose text exists and whose enrichment is unfinished is re-enqueued.
        awaiting = [
            _enrichment(DocumentStatus.EXTRACTED, EnrichmentStatus.PENDING),
            _enrichment(DocumentStatus.SUMMARISED, EnrichmentStatus.PENDING),
            _enrichment(DocumentStatus.SUMMARISED, EnrichmentStatus.ENRICHING),
        ]
        settled = [
            # Not yet extracted → no text to enrich against, held back.
            _enrichment(DocumentStatus.UPLOADED, EnrichmentStatus.PENDING),
            # Branch already terminal.
            _enrichment(DocumentStatus.SUMMARISED, EnrichmentStatus.ENRICHED),
            _enrichment(DocumentStatus.SUMMARISED, EnrichmentStatus.FAILED),
        ]
        store = {d.id: d for d in awaiting + settled}
        uow_factory = make_in_memory_uow_factory(store)

        drained: list[DocumentId] = []
        queue = JobQueue()
        await queue.start(lambda document_id: _record(drained, document_id))

        count = await reconcile_pending_enrichment(queue, uow_factory)
        await queue.join()
        await queue.stop()

        assert count == 3
        assert set(drained) == {d.id for d in awaiting}

    async def test_nothing_to_recover_returns_zero(self):
        queue = JobQueue()
        await queue.start(lambda document_id: _record([], document_id))

        count = await reconcile_pending_enrichment(queue, make_in_memory_uow_factory())

        await queue.stop()
        assert count == 0
