"""The read side: list documents, read a summary, inspect the stored artefacts —
all bypassing the bus (ADR-015/016/019)."""

import pytest

from cicero.domain.document.chapter import Chapter
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services import views

from tests.fakes import InMemoryDocumentStorage, make_in_memory_uow_factory


class TestListDocuments:
    async def test_returns_a_view_per_committed_document(self):
        uow_factory = make_in_memory_uow_factory()
        first = Document.create("Clean Code")
        second = Document.create("Refactoring")
        async with uow_factory() as uow:
            await uow.documents.save(first)
            await uow.documents.save(second)
            await uow.commit()

        documents = await views.list_documents(uow_factory)

        assert {(d.id, d.title, d.status) for d in documents} == {
            (first.id, "Clean Code", DocumentStatus.UPLOADED),
            (second.id, "Refactoring", DocumentStatus.UPLOADED),
        }

    async def test_returns_read_dtos_not_aggregates(self):
        uow_factory = make_in_memory_uow_factory()
        async with uow_factory() as uow:
            await uow.documents.save(Document.create("Clean Code"))
            await uow.commit()

        [view] = await views.list_documents(uow_factory)

        assert isinstance(view, views.DocumentView)
        assert not isinstance(view, Document)

    async def test_returns_an_empty_list_when_there_are_no_documents(self):
        assert await views.list_documents(make_in_memory_uow_factory()) == []


class TestGetDocumentSummary:
    async def test_returns_the_written_summary(self):
        # The summaries read model is written by the summarisation stage; the view
        # reads it directly, never re-deriving from the aggregate (ADR-016).
        uow_factory = make_in_memory_uow_factory()
        document = Document.create("Clean Code")
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.summaries.save(document.id, "A crisp summary.")
            await uow.commit()

        summary = await views.get_document_summary(uow_factory, document.id)

        assert isinstance(summary, views.SummaryView)
        assert summary.text == "A crisp summary."

    async def test_returns_none_when_the_document_has_no_summary(self):
        assert (
            await views.get_document_summary(
                make_in_memory_uow_factory(), DocumentId.new()
            )
            is None
        )


async def _save_extracted(uow_factory, storage) -> Document:
    """A document past extraction: its ordered chapter titles recorded and each
    chapter's Markdown blob in storage (ADR-021)."""
    document = Document.create("Clean Code")
    document.mark_extracting()
    document.mark_extracted()
    async with uow_factory() as uow:
        await uow.documents.save(document)
        await uow.chapters.save(document.id, ["Chapter One", "Chapter Two"])
        await uow.commit()
    await storage.put(document.chapter_key(0), b"Body of one.")
    await storage.put(document.chapter_key(1), b"Body of two.")
    return document


class TestGetDocumentContent:
    async def test_assembles_the_chapters_under_their_titles(self):
        # The admin content view joins the per-chapter blobs off the storage port
        # under their bookmark titles, reconstructing the whole document (ADR-021).
        uow_factory, storage = make_in_memory_uow_factory(), InMemoryDocumentStorage()
        document = await _save_extracted(uow_factory, storage)

        content = await views.get_document_content(uow_factory, storage, document.id)

        assert content == "# Chapter One\n\nBody of one.\n\n# Chapter Two\n\nBody of two."

    async def test_returns_none_before_the_document_is_extracted(self):
        # An UPLOADED document has no chapters yet — None, not an error, so
        # the route can report 404 without touching storage.
        uow_factory, storage = make_in_memory_uow_factory(), InMemoryDocumentStorage()
        document = Document.create("Clean Code")
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()

        content = await views.get_document_content(uow_factory, storage, document.id)

        assert content is None

    async def test_raises_when_the_document_is_unknown(self):
        with pytest.raises(DocumentNotFound):
            await views.get_document_content(
                make_in_memory_uow_factory(), InMemoryDocumentStorage(), DocumentId.new()
            )


class TestGetDocumentFile:
    async def test_returns_the_original_pdf_bytes_from_storage(self):
        uow_factory, storage = make_in_memory_uow_factory(), InMemoryDocumentStorage()
        document = Document.create("Clean Code")
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()
        await storage.put(document.source_key, b"%PDF-1.4 bytes")

        file = await views.get_document_file(uow_factory, storage, document.id)

        assert file == b"%PDF-1.4 bytes"

    async def test_raises_when_the_document_is_unknown(self):
        with pytest.raises(DocumentNotFound):
            await views.get_document_file(
                make_in_memory_uow_factory(), InMemoryDocumentStorage(), DocumentId.new()
            )
