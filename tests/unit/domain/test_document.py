import uuid

import pytest

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import (
    DocumentProcessingFailed,
    DocumentUploaded,
    ExtractionCompleted,
)
from cicero.domain.document.exceptions import InvalidDocumentTitle


class TestDocumentCreate:
    def test_title_is_preserved(self):
        doc = Document.create("The Pragmatic Programmer")
        assert doc.title == "The Pragmatic Programmer"

    def test_id_is_a_document_id(self):
        doc = Document.create("Any Title")
        assert isinstance(doc.id, DocumentId)
        assert isinstance(doc.id.value, uuid.UUID)

    def test_each_document_gets_a_unique_id(self):
        first = Document.create("Any Title")
        second = Document.create("Any Title")
        assert first.id != second.id

    def test_empty_title_is_rejected(self):
        with pytest.raises(InvalidDocumentTitle):
            Document.create("")

    def test_whitespace_only_title_is_rejected(self):
        with pytest.raises(InvalidDocumentTitle):
            Document.create("   ")


class TestDocumentKind:
    def test_new_document_is_a_book_by_default(self):
        # PDF uploads are books; the default is BOOK so upload need not say so (ADR-026).
        doc = Document.create("Clean Code")
        assert doc.kind is DocumentKind.BOOK

    def test_create_accepts_an_explicit_kind(self):
        # URL ingest and overrides pass the derived kind through create.
        doc = Document.create("Some Article", kind=DocumentKind.ARTICLE)
        assert doc.kind is DocumentKind.ARTICLE

    def test_kind_participates_in_equality(self):
        # kind is a plain field, so two documents differing only in kind are not
        # equal — a persisted-vs-loaded compare stays honest (ADR-026).
        book = Document.create("Same Title")
        article = Document(id=book.id, title=book.title, kind=DocumentKind.ARTICLE)
        assert book != article


class TestDocumentStatusLifecycle:
    def test_new_document_starts_uploaded(self):
        doc = Document.create("Any Title")
        assert doc.status is DocumentStatus.UPLOADED

    def test_storage_keys_are_derived_from_identity(self):
        doc = Document.create("Any Title")
        assert doc.source_key == f"documents/{doc.id.value}/source"
        assert doc.chapter_key(2) == f"documents/{doc.id.value}/chapters/2"

    def test_mark_extracting_transitions_to_extracting(self):
        doc = Document.create("Any Title")
        doc.mark_extracting()
        assert doc.status is DocumentStatus.EXTRACTING

    def test_mark_extracted_transitions_to_extracted(self):
        # Names the stage the document *finished*, not "readable": status encodes
        # pipeline position, so a later stage can follow it (ADR-014).
        doc = Document.create("Any Title")
        doc.mark_extracted()
        assert doc.status is DocumentStatus.EXTRACTED

    def test_mark_summarising_transitions_to_summarising(self):
        # mark_* is unguarded (ADR-014), so this asserts the transition alone —
        # no need to walk the prior stages, which would imply a guard that isn't there.
        doc = Document.create("Any Title")
        doc.mark_summarising()
        assert doc.status is DocumentStatus.SUMMARISING

    def test_mark_summarised_transitions_to_summarised(self):
        doc = Document.create("Any Title")
        doc.mark_summarised()
        assert doc.status is DocumentStatus.SUMMARISED

    def test_mark_failed_transitions_to_failed(self):
        # One terminal for any spine stage that fails — extraction or summarization
        # land in the same FAILED (ADR-014/016); which stage is in the logs.
        doc = Document.create("Any Title")
        doc.mark_failed()
        assert doc.status is DocumentStatus.FAILED


class TestDocumentEvents:
    def test_create_records_a_document_uploaded_event(self):
        doc = Document.create("Any Title")
        assert doc.events == [DocumentUploaded(document_id=doc.id)]

    def test_collect_events_returns_and_clears_them(self):
        doc = Document.create("Any Title")

        collected = doc.collect_events()

        assert collected == [DocumentUploaded(document_id=doc.id)]
        assert doc.events == []

    def test_mark_extracted_records_an_extraction_completed_event(self):
        doc = Document.create("Any Title")
        doc.collect_events()  # drop the creation event
        doc.mark_extracted()
        assert doc.events == [ExtractionCompleted(document_id=doc.id)]

    def test_in_flight_markers_raise_no_event(self):
        # EXTRACTING and SUMMARISING are in-flight states nothing subscribes to;
        # only creation, completion, and failure are facts worth publishing (ADR-011/016).
        doc = Document.create("Any Title")
        doc.collect_events()  # drop the creation event
        doc.mark_extracting()
        doc.mark_summarising()
        assert doc.events == []

    def test_mark_summarised_records_no_event(self):
        # SUMMARISED is the linear spine's terminal; nothing consumes it yet, so it
        # raises no event (non-speculative, ADR-016).
        doc = Document.create("Any Title")
        doc.collect_events()  # drop the creation event
        doc.mark_summarising()
        doc.mark_summarised()
        assert doc.events == []

    def test_mark_failed_records_a_document_processing_failed_event(self):
        # A single, stage-agnostic failure fact for the single FAILED terminal (ADR-016).
        doc = Document.create("Any Title")
        doc.collect_events()  # drop the creation event
        doc.mark_failed()
        assert doc.events == [DocumentProcessingFailed(document_id=doc.id)]

    def test_events_are_excluded_from_equality(self):
        # Two documents differing only in pending events are still equal, so a
        # persisted-vs-loaded comparison is unaffected (ADR-011).
        first = Document.create("Same Title")
        second = Document(id=first.id, title=first.title)
        assert first.events and not second.events
        assert first == second
