"""Status-driven enrichment branch: the edge decides the enrichment intent (ADR-028).

The readability spine's conveyor (``pipeline``), applied to the second axis. A
document's persisted ``enrichment_status`` decides whether its one enrichment stage
still owes work, so the branch's consumer derives the verb from state just as the
spine's does — no handler names it.

Recovery asks one question more. Enrichment reads the *extracted* opening text, so a
document must be text-ready as well as branch-unfinished; ``awaits_enrichment`` crosses
both axes to reconstruct exactly the set ``ExtractionCompleted`` enqueues in the live
flow. The consumer only ever sees post-extraction ids, so it keys on the branch alone.
"""

from __future__ import annotations

import logging

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.domain.messages import Command
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.job_queue import JobConsumer
from cicero.services.messagebus import MessageBus

logger = logging.getLogger(__name__)

# One stage, so this table is short — but it is the same total-over-the-enum shape as
# NEXT_COMMAND, so a new EnrichmentStatus without a decision fails a test. A transient
# ENRICHING re-runs the stage after a restart; FAILED is terminal, not retried.
NEXT_ENRICHMENT: dict[EnrichmentStatus, type[Command] | None] = {
    EnrichmentStatus.PENDING: commands.EnrichDocument,
    EnrichmentStatus.ENRICHING: commands.EnrichDocument,
    EnrichmentStatus.ENRICHED: None,
    EnrichmentStatus.FAILED: None,
}

# The spine states where extracted text exists — the moment enrichment can run.
_TEXT_READY = frozenset(
    {
        DocumentStatus.EXTRACTED,
        DocumentStatus.SUMMARISING,
        DocumentStatus.SUMMARISED,
    }
)


def next_enrichment_command(
    status: EnrichmentStatus, document_id: DocumentId
) -> Command | None:
    """The command that advances the branch, or ``None`` if enrichment is settled."""
    command_type = NEXT_ENRICHMENT[status]
    return None if command_type is None else command_type(document_id=document_id)


def has_pending_enrichment(status: EnrichmentStatus) -> bool:
    """Whether the branch still owes this document work, read off ``enrichment_status``."""
    return NEXT_ENRICHMENT[status] is not None


def awaits_enrichment(document: Document) -> bool:
    """Whether a document should be (re-)enqueued for enrichment: its text exists *and*
    the branch is unfinished. The recovery predicate — dispatch keys off the event."""
    return document.status in _TEXT_READY and has_pending_enrichment(
        document.enrichment_status
    )


def make_enrichment_consumer(
    bus: MessageBus, uow_factory: UnitOfWorkFactory
) -> JobConsumer:
    """The enrichment queue's worker: read ``enrichment_status`` back and dispatch its
    command (ADR-028). Fed only post-extraction ids, so the branch axis is enough."""

    async def consume(document_id: DocumentId) -> None:
        async with uow_factory() as uow:
            document = await uow.documents.find_by_id(document_id)

        if document is None:
            logger.info("Dropping enrichment intent for unknown document id=%s", document_id)
            return

        command = next_enrichment_command(document.enrichment_status, document_id)
        if command is None:
            logger.debug(
                "Nothing to enrich id=%s enrichment_status=%s",
                document_id,
                document.enrichment_status,
            )
            return

        await bus.handle(command)

    return consume
