"""Summarise a document → the read model — the ``SummariseDocument`` handler (ADR-016).

Drives SUMMARISING→SUMMARISED/FAILED with a stub summarizer. The summary is written to
the summaries read model in the *same* transaction as ``mark_summarised``, so it is
readable exactly when the document is SUMMARISED. An unknown id raises ``DocumentNotFound``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services import views
from cicero.services.document.summarise_document import SummariseDocument

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentSummarizer,
    make_in_memory_uow_factory,
)

_EXTRACTED_MARKDOWN = "# Clean Code\n\nBody."


async def _extracted_document(uow_factory, storage):
    """Arrange the precondition SummariseDocument consumes — a document at EXTRACTED
    with its extracted markdown in storage — built directly, not by running the
    upload+extract stages, so this suite exercises only the summarise handler."""
    document = Document.create("Clean Code")
    document.mark_extracted()
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.commit()
    await storage.put(document.content_key, _EXTRACTED_MARKDOWN.encode())
    return document


async def _summarise(uow_factory, storage, summarizer, document_id):
    await SummariseDocument(storage, summarizer)(
        commands.SummariseDocument(document_id=document_id), uow_factory()
    )


class _ExplodingSummarizer(StubDocumentSummarizer):
    async def summarize(self, markdown: str) -> str:
        raise RuntimeError("summarization failed")


class TestSummariseDocument:
    async def test_marks_the_document_summarised(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)

        await _summarise(
            uow_factory, storage, StubDocumentSummarizer("A crisp summary."), document.id
        )

        async with uow_factory() as uow:
            summarised = await uow.documents.find_by_id(document.id)
        assert summarised.status is DocumentStatus.SUMMARISED

    async def test_stores_the_summary_so_the_read_side_can_serve_it(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)

        await _summarise(
            uow_factory, storage, StubDocumentSummarizer("A crisp summary."), document.id
        )

        summary = await views.get_document_summary(uow_factory, document.id)
        assert summary.text == "A crisp summary."

    async def test_summarizes_the_extracted_markdown(self):
        # The stub records what it was handed: the stage feeds it the extracted text
        # (internal, never the source), not the raw upload bytes.
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)
        summarizer = StubDocumentSummarizer("A crisp summary.")

        await _summarise(uow_factory, storage, summarizer, document.id)

        assert summarizer.received == _EXTRACTED_MARKDOWN

    async def test_commits_summarising_before_summarization_runs(self):
        # A spy summarizer reads the persisted status mid-call: it must already be
        # SUMMARISING, i.e. committed before the heavy work begins (mirrors extraction).
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)
        seen: list[DocumentStatus] = []

        class _StatusSpySummarizer(StubDocumentSummarizer):
            async def summarize(self, markdown: str) -> str:
                async with uow_factory() as uow:
                    mid = await uow.documents.find_by_id(document.id)
                    seen.append(mid.status)
                return "summary"

        await _summarise(uow_factory, storage, _StatusSpySummarizer(), document.id)

        assert seen == [DocumentStatus.SUMMARISING]

    async def test_summarization_failure_marks_failed_and_stores_no_summary(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)

        await _summarise(uow_factory, storage, _ExplodingSummarizer(), document.id)

        async with uow_factory() as uow:
            failed = await uow.documents.find_by_id(document.id)
        assert failed.status is DocumentStatus.FAILED
        # SUMMARISED ⇔ summary readable, so a failure leaves nothing for the reader.
        assert await views.get_document_summary(uow_factory, document.id) is None

    async def test_unknown_id_raises_document_not_found(self):
        summarise = SummariseDocument(
            InMemoryDocumentStorage(), StubDocumentSummarizer("s")
        )

        with pytest.raises(DocumentNotFound):
            await summarise(
                commands.SummariseDocument(document_id=DocumentId.new()),
                make_in_memory_uow_factory()(),
            )
