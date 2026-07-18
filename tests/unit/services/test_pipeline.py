"""Upload *causes* extraction, now off the request path (ADR-012/013).

An upload raises ``DocumentUploaded``; ``EnqueueExtraction`` puts the document on the
job queue and the upload returns immediately as UPLOADED. The queue worker then issues
the ``ExtractDocument`` command, driving the document to READY — so draining the queue
advances it without the upload ever having blocked.
"""

from cicero.domain.document import commands
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import DocumentUploaded
from cicero.entrypoints.job_queue import JobQueue
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.enqueue_extraction import EnqueueExtraction
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.list_documents import ListDocuments
from cicero.services.document.upload_document import UploadDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    make_in_memory_uow_factory,
)


def _wire(uow_factory, storage, extractor) -> tuple[MessageBus, JobQueue]:
    """The full handler/queue wiring the composition root builds (ADR-011/012/013)."""
    queue = JobQueue()
    bus = MessageBus(
        uow_factory,
        command_handlers={
            commands.UploadDocument: UploadDocument(storage),
            commands.ListDocuments: ListDocuments(),
            commands.DeleteDocument: DeleteDocument(storage),
            commands.ExtractDocument: ExtractDocument(storage, extractor),
        },
        event_handlers={DocumentUploaded: [EnqueueExtraction(queue.enqueue)]},
    )
    return bus, queue


class TestUploadCausesExtraction:
    async def test_uploading_enqueues_and_the_worker_advances_to_ready(self):
        bus, queue = _wire(
            make_in_memory_uow_factory(),
            InMemoryDocumentStorage(),
            StubDocumentExtractor("# Clean Code"),
        )
        await queue.start(
            lambda document_id: bus.handle(
                commands.ExtractDocument(document_id=document_id)
            )
        )

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )
        # Extraction is off the request path: the upload result is still UPLOADED.
        assert document.status is DocumentStatus.UPLOADED

        await queue.join()
        await queue.stop()

        listed = await bus.handle(commands.ListDocuments())
        assert [d.status for d in listed] == [DocumentStatus.READY]
