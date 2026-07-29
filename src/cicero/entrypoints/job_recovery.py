from __future__ import annotations

import logging

from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.enrichment_pipeline import awaits_enrichment
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.pipeline import has_next_stage

logger = logging.getLogger(__name__)


async def reconcile_unfinished_documents(
    queue: JobQueue, uow_factory: UnitOfWorkFactory
) -> int:
    """Re-enqueue every document the pipeline still owes work, after a restart (ADR-014).

    Work is reconstructed purely from persisted status via ``has_next_stage`` — the
    same question dispatch asks — so recovery is not a special case. Returns the count.
    """
    async with uow_factory() as uow:
        documents = await uow.documents.find_all()

    enqueued = 0
    for document in documents:
        if has_next_stage(document.status):
            await queue.enqueue(document.id)
            enqueued += 1
    if enqueued:
        logger.info("Re-enqueued %d unfinished document(s) on startup", enqueued)
    return enqueued


async def reconcile_pending_enrichment(
    enrich_queue: JobQueue, uow_factory: UnitOfWorkFactory
) -> int:
    """Re-enqueue every document the enrichment branch still owes work, after a restart
    (ADR-028). The spine's mirror on the branch's own queue: it reconstructs the same
    set ``ExtractionCompleted`` enqueues live, from persisted state via ``awaits_enrichment``
    — text-ready and unfinished — so recovery is no special case here either. Returns the count.
    """
    async with uow_factory() as uow:
        documents = await uow.documents.find_all()

    enqueued = 0
    for document in documents:
        if awaits_enrichment(document):
            await enrich_queue.enqueue(document.id)
            enqueued += 1
    if enqueued:
        logger.info("Re-enqueued %d document(s) for enrichment on startup", enqueued)
    return enqueued
