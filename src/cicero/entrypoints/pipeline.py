"""Status-driven pipeline advance: the edge decides what an intent means (ADR-014).

The job queue carries bare document ids. This module holds the one table mapping a
document's **persisted status** to the command that advances it, and the consumer that
reads the status back and dispatches. Keeping both here means the pipeline's order is
written down in exactly one place, and commands are still born only in ``entrypoints``
(ADR-012) — a handler names a stage nowhere.
"""

from __future__ import annotations

import logging

from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.messages import Command
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.job_queue import JobConsumer
from cicero.services.messagebus import MessageBus

logger = logging.getLogger(__name__)

# The pipeline, as a table. ``None`` means the document is done — the intent is
# dropped. Total over ``DocumentStatus`` on purpose: a new status without a decision
# here is a document that would stall silently, so the omission fails a test instead.
# ``EXTRACTING`` maps to the same command as ``UPLOADED`` because a stage interrupted
# mid-flight is simply re-run (``mark_*`` is unguarded, ADR-002).
NEXT_COMMAND: dict[DocumentStatus, type[Command] | None] = {
    DocumentStatus.UPLOADED: commands.ExtractDocument,
    DocumentStatus.EXTRACTING: commands.ExtractDocument,
    DocumentStatus.EXTRACTED: None,
    DocumentStatus.FAILED: None,
}


def next_command(status: DocumentStatus, document_id: DocumentId) -> Command | None:
    """The command that advances a document in ``status``, or ``None`` if it is done."""
    command_type = NEXT_COMMAND[status]
    return None if command_type is None else command_type(document_id=document_id)


def has_next_stage(status: DocumentStatus) -> bool:
    """Whether the pipeline still owes this document work — the question restart
    recovery asks, so recovery and dispatch share one definition of 'unfinished'."""
    return NEXT_COMMAND[status] is not None


def make_pipeline_consumer(bus: MessageBus, uow_factory: UnitOfWorkFactory) -> JobConsumer:
    """The queue worker's job: read the document's status and dispatch the command that
    status calls for. Commands are born here, at the edge (ADR-013/014)."""

    async def consume(document_id: DocumentId) -> None:
        async with uow_factory() as uow:
            document = await uow.documents.find_by_id(document_id)

        if document is None:
            # Deleted between enqueue and dispatch; a stale intent is not an error.
            logger.info("Dropping intent for unknown document id=%s", document_id)
            return

        command = next_command(document.status, document_id)
        if command is None:
            logger.debug(
                "Nothing to advance id=%s status=%s", document_id, document.status
            )
            return

        await bus.handle(command)

    return consume
