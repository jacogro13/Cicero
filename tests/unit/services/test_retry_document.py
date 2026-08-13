"""Re-drive a failed document — the ``RetryDocument`` handler (ADR-030).

The handler resets the status and raises ``DocumentRetried``; the bus drains that
event to ``AdvanceDocument``, so the re-drive reaches the queue the same way an
upload does. An unknown id raises ``DocumentNotFound``, and a document that did not
fail raises ``DocumentNotRetryable``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import DocumentRetried
from cicero.domain.document.exceptions import DocumentNotFound, DocumentNotRetryable
from cicero.services.document.advance_document import AdvanceDocument
from cicero.services.document.retry_document import RetryDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import make_in_memory_uow_factory


def _bus(uow_factory, enqueued: list[DocumentId]) -> MessageBus:
    async def enqueue(document_id: DocumentId) -> None:
        enqueued.append(document_id)

    return MessageBus(
        uow_factory,
        command_handlers={commands.RetryDocument: RetryDocument()},
        event_handlers={DocumentRetried: [AdvanceDocument(enqueue)]},
    )


async def _saved(uow_factory, status: DocumentStatus) -> Document:
    document = Document.create("Clean Code")
    document.status = status
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.commit()
    return document


class TestRetryDocument:
    async def test_a_failed_document_with_no_chapters_returns_to_uploaded(self):
        uow_factory = make_in_memory_uow_factory()
        document = await _saved(uow_factory, DocumentStatus.FAILED)

        await _bus(uow_factory, []).handle(
            commands.RetryDocument(document_id=document.id)
        )

        async with uow_factory() as uow:
            retried = await uow.documents.find_by_id(document.id)
        assert retried.status is DocumentStatus.UPLOADED

    async def test_a_failed_document_with_chapters_resumes_at_extracted(self):
        # The chapter rows commit with mark_extracted, so their presence is the record
        # that extraction finished — the handler reads it and skips that stage (ADR-032).
        uow_factory = make_in_memory_uow_factory()
        document = await _saved(uow_factory, DocumentStatus.FAILED)
        async with uow_factory() as uow:
            await uow.chapters.save(document.id, ["Intro", "Body"])
            await uow.commit()
        enqueued: list[DocumentId] = []

        await _bus(uow_factory, enqueued).handle(
            commands.RetryDocument(document_id=document.id)
        )

        async with uow_factory() as uow:
            retried = await uow.documents.find_by_id(document.id)
        assert retried.status is DocumentStatus.EXTRACTED
        assert enqueued == [document.id]  # still reaches the queue, one stage further on

    async def test_the_retry_reaches_the_queue(self):
        # The point of the slice: the status reset alone would sit there, since nothing
        # re-drives FAILED. The event is what puts the document back on the conveyor.
        uow_factory = make_in_memory_uow_factory()
        document = await _saved(uow_factory, DocumentStatus.FAILED)
        enqueued: list[DocumentId] = []

        await _bus(uow_factory, enqueued).handle(
            commands.RetryDocument(document_id=document.id)
        )

        assert enqueued == [document.id]

    async def test_a_document_that_did_not_fail_is_refused(self):
        uow_factory = make_in_memory_uow_factory()
        document = await _saved(uow_factory, DocumentStatus.SUMMARISING)
        enqueued: list[DocumentId] = []

        with pytest.raises(DocumentNotRetryable):
            await _bus(uow_factory, enqueued).handle(
                commands.RetryDocument(document_id=document.id)
            )

        # Nothing enqueued: re-driving a stage already in flight would run it twice.
        assert enqueued == []

    async def test_unknown_id_raises_document_not_found(self):
        with pytest.raises(DocumentNotFound):
            await _bus(make_in_memory_uow_factory(), []).handle(
                commands.RetryDocument(document_id=DocumentId.new())
            )
