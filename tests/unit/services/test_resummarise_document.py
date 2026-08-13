"""Summarise a document again from scratch — the ``ResummariseDocument`` handler
(ADR-032).

The handler discards the summaries and sends the document back to ``EXTRACTED``,
raising ``SummariesDiscarded``; the bus drains that event to ``AdvanceDocument``, so the
re-summarisation reaches the queue the way a retry does. Discarding is the point:
ADR-031 skips every summary that survives, so leaving them would be a no-op. An unknown
id raises ``DocumentNotFound``, and a document that is not ``SUMMARISED`` raises
``DocumentNotRetryable``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import SummariesDiscarded
from cicero.domain.document.exceptions import DocumentNotFound, DocumentNotRetryable
from cicero.services.document.advance_document import AdvanceDocument
from cicero.services.document.resummarise_document import ResummariseDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import make_in_memory_uow_factory


def _bus(uow_factory, enqueued: list[DocumentId]) -> MessageBus:
    async def enqueue(document_id: DocumentId) -> None:
        enqueued.append(document_id)

    return MessageBus(
        uow_factory,
        command_handlers={commands.ResummariseDocument: ResummariseDocument()},
        event_handlers={SummariesDiscarded: [AdvanceDocument(enqueue)]},
    )


async def _summarised(uow_factory, status=DocumentStatus.SUMMARISED) -> Document:
    """A document with chapters and a summary for each — what the operator is asking
    to have redone."""
    document = Document.create("Clean Code")
    document.status = status
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.chapters.save(document.id, ["Intro", "Body"])
        await uow.summaries.save(document.id, 0, "old summary of Intro")
        await uow.summaries.save(document.id, 1, "old summary of Body")
        await uow.commit()
    return document


class TestResummariseDocument:
    async def test_the_summaries_are_discarded(self):
        # Not a detail of the reset: with them in place the re-run would skip every
        # chapter (ADR-031) and the operator would get the same summaries back.
        uow_factory = make_in_memory_uow_factory()
        document = await _summarised(uow_factory)

        await _bus(uow_factory, []).handle(
            commands.ResummariseDocument(document_id=document.id)
        )

        async with uow_factory() as uow:
            assert await uow.summaries.all(document.id) == {}

    async def test_the_document_waits_at_extracted_with_its_chapters(self):
        uow_factory = make_in_memory_uow_factory()
        document = await _summarised(uow_factory)

        await _bus(uow_factory, []).handle(
            commands.ResummariseDocument(document_id=document.id)
        )

        async with uow_factory() as uow:
            reset = await uow.documents.find_by_id(document.id)
            # The chapters stay: they are the input to the stage being redone.
            assert await uow.chapters.list(document.id) == ["Intro", "Body"]
        assert reset.status is DocumentStatus.EXTRACTED

    async def test_the_re_summarisation_reaches_the_queue(self):
        uow_factory = make_in_memory_uow_factory()
        document = await _summarised(uow_factory)
        enqueued: list[DocumentId] = []

        await _bus(uow_factory, enqueued).handle(
            commands.ResummariseDocument(document_id=document.id)
        )

        assert enqueued == [document.id]

    async def test_a_document_that_is_not_summarised_is_refused(self):
        uow_factory = make_in_memory_uow_factory()
        document = await _summarised(uow_factory, status=DocumentStatus.SUMMARISING)
        enqueued: list[DocumentId] = []

        with pytest.raises(DocumentNotRetryable):
            await _bus(uow_factory, enqueued).handle(
                commands.ResummariseDocument(document_id=document.id)
            )

        assert enqueued == []

    async def test_a_refused_resummarise_keeps_the_summaries(self):
        # The guard runs before the delete, so a 409 costs nothing. The other order
        # would throw away a book's summaries on a rejected request.
        uow_factory = make_in_memory_uow_factory()
        document = await _summarised(uow_factory, status=DocumentStatus.EXTRACTING)

        with pytest.raises(DocumentNotRetryable):
            await _bus(uow_factory, []).handle(
                commands.ResummariseDocument(document_id=document.id)
            )

        async with uow_factory() as uow:
            assert len(await uow.summaries.all(document.id)) == 2

    async def test_unknown_id_raises_document_not_found(self):
        with pytest.raises(DocumentNotFound):
            await _bus(make_in_memory_uow_factory(), []).handle(
                commands.ResummariseDocument(document_id=DocumentId.new())
            )
