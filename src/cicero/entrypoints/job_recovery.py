from __future__ import annotations

import logging

from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.pipeline import has_next_stage

logger = logging.getLogger(__name__)


async def reconcile_unfinished_documents(
    queue: JobQueue, uow_factory: UnitOfWorkFactory
) -> int:
    """Re-enqueue every document the pipeline still owes work, after a restart (ADR-014).

    The in-process queue loses whatever it held on a crash or restart. Work is
    reconstructed purely from persisted status — no jobs table — and by asking
    ``has_next_stage`` this is the *same* question ordinary dispatch asks, so recovery
    is no longer a special case: it re-runs an interrupted stage and also picks up a
    document whose enqueue never happened. Returns the count enqueued.
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
