from __future__ import annotations

import logging

from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.job_queue import JobQueue

logger = logging.getLogger(__name__)


async def reconcile_processing_documents(
    queue: JobQueue, uow_factory: UnitOfWorkFactory
) -> int:
    """Re-enqueue extraction for documents left mid-flight by a restart (ADR-013).

    The in-process queue loses whatever was running on a crash or restart. Work is
    reconstructed purely from persisted status — no jobs table: a document still in
    ``PROCESSING`` never finished extracting, so re-enqueue it (``mark_processing``
    is unguarded, so re-running is safe). Returns the count enqueued.
    """
    async with uow_factory() as uow:
        documents = await uow.documents.find_all()

    enqueued = 0
    for document in documents:
        if document.status is DocumentStatus.PROCESSING:
            await queue.enqueue(document.id)
            enqueued += 1
    if enqueued:
        logger.info("Re-enqueued %d interrupted extraction(s) on startup", enqueued)
    return enqueued
