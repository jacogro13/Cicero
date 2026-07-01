"""Upload *causes* extraction — the pipeline as events (ADR-012).

Extraction is the ``DocumentUploaded`` event handler, so an upload through a wired
bus reaches READY; the echoed create result still reflects creation (UPLOADED),
since extraction drives a freshly loaded aggregate, not the returned one.
"""

from cicero.domain.document import commands
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import DocumentUploaded
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.list_documents import ListDocuments
from cicero.services.document.upload_document import UploadDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    make_in_memory_uow_factory,
)


def _wired_bus(uow_factory, storage, extractor) -> MessageBus:
    """The full handler/event wiring the composition root builds (ADR-011/012)."""
    return MessageBus(
        uow_factory,
        command_handlers={
            commands.UploadDocument: UploadDocument(storage),
            commands.ListDocuments: ListDocuments(),
            commands.DeleteDocument: DeleteDocument(storage),
        },
        event_handlers={DocumentUploaded: [ExtractDocument(storage, extractor)]},
    )


class TestUploadCausesExtraction:
    async def test_uploading_advances_the_document_to_ready(self):
        bus = _wired_bus(
            make_in_memory_uow_factory(),
            InMemoryDocumentStorage(),
            StubDocumentExtractor("# Clean Code"),
        )

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )

        listed = await bus.handle(commands.ListDocuments())
        assert [d.status for d in listed] == [DocumentStatus.READY]
        # The echoed create result reflects creation, not the downstream extraction.
        assert document.status is DocumentStatus.UPLOADED
