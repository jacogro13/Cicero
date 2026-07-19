"""The stage table: persisted status decides the next command (ADR-014).

This is the only place the pipeline's order is written down, so it is asserted
directly — every status maps to a command or to nothing, and a status that gains a
stage later only needs a new entry here. The consumer is the edge that reads the
status back and issues that command, so no handler ever names a verb (ADR-012).
"""

from __future__ import annotations

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.messages import Message
from cicero.entrypoints.pipeline import (
    NEXT_COMMAND,
    has_next_stage,
    make_pipeline_consumer,
    next_command,
)

from tests.fakes import make_in_memory_uow_factory


class RecordingBus:
    """Stands in for the message bus: records what the edge dispatched."""

    def __init__(self) -> None:
        self.handled: list[Message] = []

    async def handle(self, message: Message) -> None:
        self.handled.append(message)


def _document(status: DocumentStatus) -> Document:
    document = Document.create("Clean Code")
    document.status = status
    return document


class TestStageTable:
    def test_every_status_is_accounted_for(self):
        # Total over the enum: adding a status without deciding its next stage
        # fails here rather than silently stalling a document.
        assert set(NEXT_COMMAND) == set(DocumentStatus)

    @pytest.mark.parametrize(
        "status",
        [DocumentStatus.UPLOADED, DocumentStatus.EXTRACTING],
    )
    def test_pending_extraction_advances_to_extract_document(self, status):
        document_id = DocumentId.new()

        assert next_command(status, document_id) == commands.ExtractDocument(
            document_id=document_id
        )
        assert has_next_stage(status)

    @pytest.mark.parametrize(
        "status",
        [DocumentStatus.EXTRACTED, DocumentStatus.FAILED],
    )
    def test_terminal_statuses_have_no_next_command(self, status):
        assert next_command(status, DocumentId.new()) is None
        assert not has_next_stage(status)

    def test_extracting_re_advances_so_an_interrupted_stage_reruns(self):
        # A document caught mid-extraction by a restart is not terminal: re-reading
        # its status yields the same command, which is how recovery collapses into
        # ordinary dispatch (ADR-014).
        document_id = DocumentId.new()
        assert next_command(DocumentStatus.EXTRACTING, document_id) == next_command(
            DocumentStatus.UPLOADED, document_id
        )


class TestPipelineConsumer:
    async def test_derives_the_command_from_the_persisted_status(self):
        document = _document(DocumentStatus.UPLOADED)
        bus = RecordingBus()
        consume = make_pipeline_consumer(
            bus, make_in_memory_uow_factory({document.id: document})
        )

        await consume(document.id)

        # The intent carried an id only; the verb came from the database.
        assert bus.handled == [commands.ExtractDocument(document_id=document.id)]

    async def test_a_terminal_document_dispatches_nothing(self):
        document = _document(DocumentStatus.EXTRACTED)
        bus = RecordingBus()
        consume = make_pipeline_consumer(
            bus, make_in_memory_uow_factory({document.id: document})
        )

        await consume(document.id)

        assert bus.handled == []

    async def test_an_unknown_id_is_dropped_rather_than_raising(self):
        # The document was deleted between enqueue and dispatch — a stale intent
        # must not kill the worker.
        bus = RecordingBus()
        consume = make_pipeline_consumer(bus, make_in_memory_uow_factory())

        await consume(DocumentId.new())

        assert bus.handled == []
