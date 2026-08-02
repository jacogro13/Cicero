"""Summarise a document → per-chapter read models — the ``SummariseDocument`` handler
(ADR-016/021).

Drives SUMMARISING→SUMMARISED/FAILED with a stub summarizer, summarising each chapter
from its own stored Markdown. The summaries are written in the *same* transaction as
``mark_summarised``, so they are readable exactly when the document is SUMMARISED. An
unknown id raises ``DocumentNotFound``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.chapter import Chapter
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

_CHAPTERS = [Chapter("Intro", "Intro body."), Chapter("Body", "Body text.")]


async def _extracted_document(uow_factory, storage):
    """Arrange the precondition SummariseDocument consumes — a document at EXTRACTED
    with its chapters in storage — built directly, not by running the upload+extract
    stages, so this suite exercises only the summarise handler."""
    document = Document.create("Clean Code")
    document.mark_extracted()
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.chapters.save(document.id, [c.title for c in _CHAPTERS])
        await uow.commit()
    for index, chapter in enumerate(_CHAPTERS):
        await storage.put(document.chapter_key(index), chapter.markdown.encode())
    return document


async def _summarise(uow_factory, storage, summarizer, document_id):
    await SummariseDocument(storage, summarizer)(
        commands.SummariseDocument(document_id=document_id), uow_factory()
    )


class _EchoSummarizer(StubDocumentSummarizer):
    """Summarises each chapter to a marker of its own content, so per-chapter
    routing is observable."""

    async def summarize(self, markdown: str) -> str:
        return f"summary of: {markdown}"


class _ExplodingSummarizer(StubDocumentSummarizer):
    async def summarize(self, markdown: str) -> str:
        raise RuntimeError("summarization failed")


class _DeletingExplodingSummarizer(StubDocumentSummarizer):
    """A concurrent DELETE lands *and* summarization fails — the intersection of the
    two paths the suite otherwise covers only separately."""

    def __init__(self, uow_factory, document_id) -> None:
        super().__init__("s")
        self._uow_factory = uow_factory
        self._document_id = document_id

    async def summarize(self, markdown: str) -> str:
        async with self._uow_factory() as uow:
            await uow.documents.delete(await uow.documents.find_by_id(self._document_id))
            await uow.commit()
        raise RuntimeError("summarization failed")


class TestSummariseDocument:
    async def test_marks_the_document_summarised(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)

        await _summarise(uow_factory, storage, StubDocumentSummarizer("s"), document.id)

        async with uow_factory() as uow:
            summarised = await uow.documents.find_by_id(document.id)
        assert summarised.status is DocumentStatus.SUMMARISED

    async def test_summarises_each_chapter_from_its_own_content(self):
        # Each chapter is summarised from its own stored Markdown and the results are
        # served back per chapter, in order (ADR-021).
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)

        await _summarise(uow_factory, storage, _EchoSummarizer(), document.id)

        chapters = await views.get_document_chapters(uow_factory, document.id)
        assert [(c.title, c.summary) for c in chapters] == [
            ("Intro", "summary of: Intro body."),
            ("Body", "summary of: Body text."),
        ]

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

        # One entry per chapter, all observed while already SUMMARISING.
        assert seen == [DocumentStatus.SUMMARISING, DocumentStatus.SUMMARISING]

    async def test_summarization_failure_marks_failed_and_stores_no_summary(self):
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)

        await _summarise(uow_factory, storage, _ExplodingSummarizer(), document.id)

        async with uow_factory() as uow:
            failed = await uow.documents.find_by_id(document.id)
        assert failed.status is DocumentStatus.FAILED
        # SUMMARISED ⇔ summaries readable, so a failure leaves nothing for the reader.
        assert await views.get_document_summary(uow_factory, document.id) is None

    async def test_delete_mid_summarisation_stops_early_and_drops(self):
        # A DELETE lands after the first chapter: the stage must stop before summarising
        # the rest (bounded wasted work), not crash, not resurrect the document, and
        # persist no summaries for the deleted document (ADR-014).
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)  # two chapters
        seen: list[str] = []

        class _DeleteAfterFirstChapter(StubDocumentSummarizer):
            async def summarize(self, markdown: str) -> str:
                seen.append(markdown)
                if len(seen) == 1:
                    async with uow_factory() as uow:
                        doc = await uow.documents.find_by_id(document.id)
                        await uow.documents.delete(doc)
                        await uow.commit()
                return "s"

        await _summarise(uow_factory, storage, _DeleteAfterFirstChapter(), document.id)

        assert len(seen) == 1  # the second chapter is never summarised
        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None
            # Asserted on the projection, not through the view: with the document
            # gone the view answers DocumentNotFound, which would hide whether a
            # summary row was left behind.
            assert await uow.summaries.all(document.id) == {}

    async def test_delete_while_summarization_fails_drops_without_masking_the_failure(self):
        # Mirrors extraction: the failure path re-reads the document to mark it FAILED,
        # and a DELETE that won the race leaves nothing to mark. Dropping is not an
        # error (ADR-014); raising would replace the RuntimeError that failed the stage.
        uow_factory = make_in_memory_uow_factory()
        storage = InMemoryDocumentStorage()
        document = await _extracted_document(uow_factory, storage)
        summarizer = _DeletingExplodingSummarizer(uow_factory, document.id)

        await _summarise(uow_factory, storage, summarizer, document.id)

        async with uow_factory() as uow:
            assert await uow.documents.find_by_id(document.id) is None

    async def test_unknown_id_raises_document_not_found(self):
        summarise = SummariseDocument(
            InMemoryDocumentStorage(), StubDocumentSummarizer("s")
        )

        with pytest.raises(DocumentNotFound):
            await summarise(
                commands.SummariseDocument(document_id=DocumentId.new()),
                make_in_memory_uow_factory()(),
            )
