"""Status-driven pipeline advance: the edge decides what an intent means (ADR-014).

Holds the one table mapping a document's persisted status to the command that
advances it, plus the consumer that reads the status back and dispatches (ADR-012).
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

# The pipeline, as a table. ``None`` means done (intent dropped). Total over
# ``DocumentStatus`` on purpose, so a new status without a decision fails a test.
# An in-flight status re-runs its stage (``mark_*`` is unguarded, ADR-002).
NEXT_COMMAND: dict[DocumentStatus, type[Command] | None] = {
    DocumentStatus.UPLOADED: commands.ExtractDocument,
    DocumentStatus.EXTRACTING: commands.ExtractDocument,
    DocumentStatus.EXTRACTED: commands.SummariseDocument,
    DocumentStatus.SUMMARISING: commands.SummariseDocument,
    DocumentStatus.SUMMARISED: None,
    DocumentStatus.FAILED: None,
}


def next_command(status: DocumentStatus, document_id: DocumentId) -> Command | None:
    """The command that advances a document in ``status``, or ``None`` if it is done."""
    command_type = NEXT_COMMAND[status]
    return None if command_type is None else command_type(document_id=document_id)


def has_next_stage(status: DocumentStatus) -> bool:
    """Whether the pipeline still owes this document work (shared by dispatch and recovery)."""
    return NEXT_COMMAND[status] is not None


def make_pipeline_consumer(bus: MessageBus, uow_factory: UnitOfWorkFactory) -> JobConsumer:
    """The queue worker's job: read the document's status and dispatch its command
    (ADR-013/014)."""

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
