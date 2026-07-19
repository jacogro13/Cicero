"""One handler advances the pipeline, whatever the stage (ADR-014).

``AdvanceDocument`` replaces ``EnqueueExtraction``: it enqueues the document id off
any pipeline event and names no verb, so a new stage costs a subscription rather
than a handler class. What happens next is the edge's business (see
``tests/unit/entrypoints/test_pipeline.py``).
"""

from __future__ import annotations

import pytest

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import (
    DocumentEvent,
    DocumentUploaded,
    ExtractionCompleted,
)
from cicero.services.document.advance_document import AdvanceDocument

from tests.fakes import make_in_memory_uow_factory


class TestAdvanceDocument:
    @pytest.mark.parametrize("event_type", [DocumentUploaded, ExtractionCompleted])
    async def test_enqueues_the_document_id_for_any_pipeline_event(self, event_type):
        enqueued: list[DocumentId] = []
        document_id = DocumentId.new()

        async def enqueue(document_id: DocumentId) -> None:
            enqueued.append(document_id)

        handler = AdvanceDocument(enqueue)

        await handler(event_type(document_id=document_id), make_in_memory_uow_factory()())

        assert enqueued == [document_id]

    def test_pipeline_events_share_a_base_carrying_the_document_id(self):
        # The handler is typed on that base rather than on one concrete event,
        # which is what lets a later stage subscribe without changing it.
        assert issubclass(DocumentUploaded, DocumentEvent)
        assert issubclass(ExtractionCompleted, DocumentEvent)
