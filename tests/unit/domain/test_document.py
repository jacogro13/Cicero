import uuid

import pytest

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId


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
        with pytest.raises(ValueError):
            Document.create("")

    def test_whitespace_only_title_is_rejected(self):
        with pytest.raises(ValueError):
            Document.create("   ")
