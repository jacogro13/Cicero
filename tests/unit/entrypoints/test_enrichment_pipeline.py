"""The enrichment branch's stage table: persisted ``enrichment_status`` decides the
next command (ADR-028).

The readability spine's conveyor (test_pipeline), applied to the second axis. It is a
one-stage branch, so the table is short — but it is the same total-over-the-enum shape,
and the consumer is the edge that reads ``enrichment_status`` back and issues the verb,
so no handler names it.
"""

from __future__ import annotations

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.domain.messages import Message
from cicero.entrypoints.enrichment_pipeline import (
    NEXT_ENRICHMENT,
    awaits_enrichment,
    has_pending_enrichment,
    make_enrichment_consumer,
    next_enrichment_command,
)

from tests.fakes import make_in_memory_uow_factory


class RecordingBus:
    def __init__(self) -> None:
        self.handled: list[Message] = []

    async def handle(self, message: Message) -> None:
        self.handled.append(message)


def _document(
    enrichment_status: EnrichmentStatus,
    status: DocumentStatus = DocumentStatus.EXTRACTED,
) -> Document:
    document = Document.create("Clean Code")
    document.status = status
    document.enrichment_status = enrichment_status
    return document


class TestEnrichmentStageTable:
    def test_every_enrichment_status_is_accounted_for(self):
        # Total over the enum: a new status without a decision fails here.
        assert set(NEXT_ENRICHMENT) == set(EnrichmentStatus)

    @pytest.mark.parametrize(
        "status", [EnrichmentStatus.PENDING, EnrichmentStatus.ENRICHING]
    )
    def test_unfinished_enrichment_advances_to_enrich_document(self, status):
        document_id = DocumentId.new()

        assert next_enrichment_command(status, document_id) == commands.EnrichDocument(
            document_id=document_id
        )
        assert has_pending_enrichment(status)

    @pytest.mark.parametrize(
        "status", [EnrichmentStatus.ENRICHED, EnrichmentStatus.FAILED]
    )
    def test_terminal_enrichment_statuses_have_no_next_command(self, status):
        assert next_enrichment_command(status, DocumentId.new()) is None
        assert not has_pending_enrichment(status)

    def test_enriching_re_advances_so_an_interrupted_stage_reruns(self):
        # A document caught mid-enrichment by a restart re-runs the stage — the same
        # collapse of recovery into ordinary dispatch the spine does (ADR-014).
        document_id = DocumentId.new()
        assert next_enrichment_command(
            EnrichmentStatus.ENRICHING, document_id
        ) == next_enrichment_command(EnrichmentStatus.PENDING, document_id)


class TestAwaitsEnrichment:
    """The recovery predicate crosses both axes: enrichment reads extracted text, so a
    document is only (re-)enqueued once its text exists *and* the branch owes it work."""

    @pytest.mark.parametrize(
        "status",
        [
            DocumentStatus.EXTRACTED,
            DocumentStatus.SUMMARISING,
            DocumentStatus.SUMMARISED,
        ],
    )
    def test_text_ready_and_pending_is_awaiting(self, status):
        assert awaits_enrichment(_document(EnrichmentStatus.PENDING, status))

    @pytest.mark.parametrize(
        "status", [DocumentStatus.UPLOADED, DocumentStatus.EXTRACTING]
    )
    def test_before_extraction_is_not_awaiting_even_when_pending(self, status):
        # Enqueuing an un-extracted document would enrich against missing text and
        # burn the one PENDING→FAILED transition it gets — so it is held back.
        assert not awaits_enrichment(_document(EnrichmentStatus.PENDING, status))

    def test_already_enriched_is_not_awaiting(self):
        assert not awaits_enrichment(_document(EnrichmentStatus.ENRICHED))

    def test_failed_enrichment_is_terminal_not_awaiting(self):
        assert not awaits_enrichment(_document(EnrichmentStatus.FAILED))


class TestEnrichmentConsumer:
    async def test_derives_enrich_document_from_the_persisted_status(self):
        document = _document(EnrichmentStatus.PENDING)
        bus = RecordingBus()
        consume = make_enrichment_consumer(
            bus, make_in_memory_uow_factory({document.id: document})
        )

        await consume(document.id)

        assert bus.handled == [commands.EnrichDocument(document_id=document.id)]

    async def test_a_finished_enrichment_dispatches_nothing(self):
        document = _document(EnrichmentStatus.ENRICHED)
        bus = RecordingBus()
        consume = make_enrichment_consumer(
            bus, make_in_memory_uow_factory({document.id: document})
        )

        await consume(document.id)

        assert bus.handled == []

    async def test_an_unknown_id_is_dropped_rather_than_raising(self):
        bus = RecordingBus()
        consume = make_enrichment_consumer(bus, make_in_memory_uow_factory())

        await consume(DocumentId.new())

        assert bus.handled == []
