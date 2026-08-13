import uuid

import pytest

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.enrichment_status import EnrichmentStatus
from cicero.domain.document.events import (
    DocumentProcessingFailed,
    DocumentRetried,
    DocumentUploaded,
    ExtractionCompleted,
    SummariesDiscarded,
)
from cicero.domain.document.exceptions import (
    DocumentNotRetryable,
    InvalidDocumentTitle,
    InvalidDocumentUrl,
)


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


class TestDocumentFromUrl:
    def test_a_url_document_is_an_article(self):
        doc = Document.create_from_url("https://example.com/blog/clean-architecture")
        assert doc.kind is DocumentKind.ARTICLE

    def test_the_url_is_kept_as_the_source(self):
        # No blob to upload — the link is the source the worker later fetches (ADR-027).
        doc = Document.create_from_url("https://example.com/blog/clean-architecture")
        assert doc.source_url == "https://example.com/blog/clean-architecture"

    def test_an_uploaded_document_has_no_source_url(self):
        # The blob path is the discriminator's other branch: source_url is None (ADR-027).
        assert Document.create("Clean Code").source_url is None

    def test_kind_can_be_overridden_at_ingest(self):
        # The source-derived default (ARTICLE for a URL) is overridable (ADR-026).
        doc = Document.create_from_url("https://example.com/a", kind=DocumentKind.BOOK)
        assert doc.kind is DocumentKind.BOOK

    def test_title_is_derived_from_the_url(self):
        doc = Document.create_from_url("https://example.com/blog/clean-architecture")
        assert doc.title == "Clean Architecture"

    def test_title_falls_back_to_the_host_when_there_is_no_path(self):
        doc = Document.create_from_url("https://example.com/")
        assert doc.title == "example.com"

    def test_a_url_document_records_an_upload_event(self):
        # It enters the same pipeline as an upload, so it raises the same event (ADR-011).
        doc = Document.create_from_url("https://example.com/blog/clean-architecture")
        assert doc.events == [DocumentUploaded(document_id=doc.id)]

    def test_a_non_http_scheme_is_rejected(self):
        with pytest.raises(InvalidDocumentUrl):
            Document.create_from_url("ftp://example.com/file")

    def test_a_url_without_a_host_is_rejected(self):
        with pytest.raises(InvalidDocumentUrl):
            Document.create_from_url("https:///no-host")


class TestDocumentKind:
    def test_new_document_is_a_book_by_default(self):
        # PDF uploads are books; the default is BOOK so upload need not say so (ADR-026).
        doc = Document.create("Clean Code")
        assert doc.kind is DocumentKind.BOOK

    def test_create_accepts_an_explicit_kind(self):
        # URL ingest and overrides pass the derived kind through create.
        doc = Document.create("Some Article", kind=DocumentKind.ARTICLE)
        assert doc.kind is DocumentKind.ARTICLE

    def test_set_kind_corrects_a_misclassification(self):
        # kind is browsing-only, so correcting it is a plain mutation — no event, no
        # pipeline effect (ADR-026).
        doc = Document.create("An Article", kind=DocumentKind.ARTICLE)
        doc.collect_events()  # drop the creation event

        doc.set_kind(DocumentKind.BOOK)

        assert doc.kind is DocumentKind.BOOK
        assert doc.events == []

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


class TestDocumentRetry:
    def test_retry_returns_a_document_that_extracted_nothing_to_the_start(self):
        # Nothing completed, so the re-drive restarts the spine; deterministic keys
        # make that an overwrite, never a duplicate (ADR-030).
        doc = Document.create("Any Title")
        doc.mark_failed()

        doc.retry(extraction_complete=False)

        assert doc.status is DocumentStatus.UPLOADED

    def test_retry_resumes_at_extracted_when_extraction_completed(self):
        # The furthest completed stage is the resume point: re-extracting a source that
        # already yielded its chapters is minutes spent to reproduce them (ADR-032).
        doc = Document.create("Any Title")
        doc.mark_failed()

        doc.retry(extraction_complete=True)

        assert doc.status is DocumentStatus.EXTRACTED

    def test_retry_records_a_document_retried_event(self):
        doc = Document.create("Any Title")
        doc.mark_failed()
        doc.collect_events()

        doc.retry(extraction_complete=False)

        assert doc.events == [DocumentRetried(document_id=doc.id)]

    @pytest.mark.parametrize(
        "status",
        [
            DocumentStatus.UPLOADED,
            DocumentStatus.EXTRACTING,
            DocumentStatus.EXTRACTED,
            DocumentStatus.SUMMARISING,
            DocumentStatus.SUMMARISED,
        ],
    )
    def test_retrying_anything_but_a_failed_document_is_refused(self, status):
        # The one guarded transition: its caller is a person, not the pipeline, so a
        # wrong call is a client error rather than a re-run (ADR-030).
        doc = Document.create("Any Title")
        doc.status = status

        with pytest.raises(DocumentNotRetryable):
            doc.retry(extraction_complete=False)

    def test_a_refused_retry_leaves_the_status_and_events_alone(self):
        doc = Document.create("Any Title")
        doc.mark_summarised()
        doc.collect_events()

        with pytest.raises(DocumentNotRetryable):
            doc.retry(extraction_complete=True)

        assert doc.status is DocumentStatus.SUMMARISED
        assert doc.events == []


class TestDocumentResummarise:
    def test_a_summarised_document_goes_back_to_extracted(self):
        # One stage back, not to the start: the chapters are what summarisation
        # consumes, and they are still there (ADR-032).
        doc = Document.create("Any Title")
        doc.mark_summarised()

        doc.resummarise()

        assert doc.status is DocumentStatus.EXTRACTED

    def test_resummarise_records_a_summaries_discarded_event(self):
        doc = Document.create("Any Title")
        doc.mark_summarised()
        doc.collect_events()

        doc.resummarise()

        assert doc.events == [SummariesDiscarded(document_id=doc.id)]

    @pytest.mark.parametrize(
        "status",
        [
            DocumentStatus.UPLOADED,
            DocumentStatus.EXTRACTING,
            DocumentStatus.EXTRACTED,
            DocumentStatus.SUMMARISING,
            DocumentStatus.FAILED,
        ],
    )
    def test_resummarising_anything_but_a_summarised_document_is_refused(self, status):
        # Guarded like retry, and for the same reason: a person issues it. FAILED is
        # refused too — that one is retry's, and it resumes rather than redoes.
        doc = Document.create("Any Title")
        doc.status = status

        with pytest.raises(DocumentNotRetryable):
            doc.resummarise()

    def test_a_refused_resummarise_leaves_the_status_and_events_alone(self):
        doc = Document.create("Any Title")
        doc.mark_extracted()
        doc.collect_events()

        with pytest.raises(DocumentNotRetryable):
            doc.resummarise()

        assert doc.status is DocumentStatus.EXTRACTED
        assert doc.events == []


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


class TestDocumentEnrichment:
    def test_new_document_is_pending_enrichment(self):
        # A separate axis from status — a fresh document owes both a summary and
        # enrichment, tracked independently (ADR-028).
        doc = Document.create("Any Title")
        assert doc.enrichment_status is EnrichmentStatus.PENDING

    def test_enrichment_fields_start_empty(self):
        doc = Document.create("Any Title")
        assert doc.authors is None
        assert doc.year is None
        assert doc.has_cover is False

    def test_cover_key_is_derived_from_identity(self):
        doc = Document.create("Any Title")
        assert doc.cover_key == f"documents/{doc.id.value}/cover"

    def test_mark_enriching_transitions_to_enriching(self):
        doc = Document.create("Any Title")
        doc.mark_enriching()
        assert doc.enrichment_status is EnrichmentStatus.ENRICHING

    def test_apply_enrichment_fills_the_metadata(self):
        doc = Document.create("Any Title")
        doc.apply_enrichment(authors="Jane Doe", year=1998, has_cover=True)
        assert doc.authors == "Jane Doe"
        assert doc.year == 1998
        assert doc.has_cover is True

    def test_mark_enriched_transitions_to_enriched(self):
        doc = Document.create("Any Title")
        doc.mark_enriched()
        assert doc.enrichment_status is EnrichmentStatus.ENRICHED

    def test_mark_enrichment_failed_transitions_to_failed(self):
        # Best-effort: a failed enrichment never touches the readability spine.
        doc = Document.create("Any Title")
        doc.mark_enrichment_failed()
        assert doc.enrichment_status is EnrichmentStatus.FAILED
        assert doc.status is DocumentStatus.UPLOADED

    def test_enrichment_transitions_raise_no_events(self):
        # The branch is terminal — nothing downstream reacts (ADR-028).
        doc = Document.create("Any Title")
        doc.collect_events()  # drop the creation event
        doc.mark_enriching()
        doc.apply_enrichment(authors="Jane Doe", year=1998, has_cover=True)
        doc.mark_enriched()
        assert doc.events == []
