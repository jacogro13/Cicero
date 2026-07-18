"""Restart recovery: re-enqueue documents left mid-extraction (ADR-013).

Only documents persisted as PROCESSING are re-enqueued — reconstructed from status
alone, with no jobs table.
"""

from __future__ import annotations

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.job_recovery import reconcile_processing_documents

from tests.fakes import make_in_memory_uow_factory


def _document(status: DocumentStatus) -> Document:
    document = Document.create("Clean Code")
    document.status = status
    return document


async def _record(sink: list, value) -> None:
    sink.append(value)


class TestReconcileProcessingDocuments:
    async def test_reenqueues_only_processing_documents(self):
        processing = [_document(DocumentStatus.PROCESSING) for _ in range(2)]
        others = [
            _document(DocumentStatus.UPLOADED),
            _document(DocumentStatus.READY),
            _document(DocumentStatus.FAILED),
        ]
        store = {d.id: d for d in processing + others}
        uow_factory = make_in_memory_uow_factory(store)

        drained: list[DocumentId] = []
        queue = JobQueue()
        await queue.start(lambda document_id: _record(drained, document_id))

        count = await reconcile_processing_documents(queue, uow_factory)
        await queue.join()
        await queue.stop()

        assert count == 2
        assert set(drained) == {d.id for d in processing}

    async def test_nothing_to_recover_returns_zero(self):
        queue = JobQueue()
        await queue.start(lambda document_id: _record([], document_id))

        count = await reconcile_processing_documents(queue, make_in_memory_uow_factory())

        await queue.stop()
        assert count == 0
