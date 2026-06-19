import uuid

import pytest

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.document_status import DocumentStatus
from pagemaster.domain.document.exceptions import InvalidDocumentTitle


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


class TestDocumentStatusLifecycle:
    def test_new_document_starts_uploaded(self):
        doc = Document.create("Any Title")
        assert doc.status is DocumentStatus.UPLOADED

    def test_storage_keys_are_derived_from_identity(self):
        doc = Document.create("Any Title")
        assert doc.source_key == f"documents/{doc.id.value}/source"
        assert doc.content_key == f"documents/{doc.id.value}/content"

    def test_mark_processing_transitions_to_processing(self):
        doc = Document.create("Any Title")
        doc.mark_processing()
        assert doc.status is DocumentStatus.PROCESSING

    def test_mark_ready_transitions_to_ready(self):
        doc = Document.create("Any Title")
        doc.mark_processing()
        doc.mark_ready()
        assert doc.status is DocumentStatus.READY

    def test_mark_failed_transitions_to_failed(self):
        doc = Document.create("Any Title")
        doc.mark_processing()
        doc.mark_failed()
        assert doc.status is DocumentStatus.FAILED
