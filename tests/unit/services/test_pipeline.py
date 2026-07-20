"""Upload *causes* extraction, off the request path and driven by status (ADR-012/013/014).

An upload raises ``DocumentUploaded``; ``AdvanceDocument`` puts the document id on the
job queue and the upload returns immediately as UPLOADED. The worker then reads the
document's persisted status back and issues the command that status calls for — so
draining the queue advances the pipeline without the upload ever having blocked, and
without any handler naming a verb.
"""

from cicero.domain.document import commands
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import DocumentUploaded
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.pipeline import make_pipeline_consumer
from cicero.services.document.advance_document import AdvanceDocument
from cicero.services import views
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.upload_document import UploadDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    make_in_memory_uow_factory,
)


def _wire(uow_factory, storage, extractor) -> tuple[MessageBus, JobQueue]:
    """The full handler/queue wiring the composition root builds (ADR-011/012/013/014)."""
    queue = JobQueue()
    bus = MessageBus(
        uow_factory,
        command_handlers={
            commands.UploadDocument: UploadDocument(storage),
            commands.DeleteDocument: DeleteDocument(storage),
            commands.ExtractDocument: ExtractDocument(storage, extractor),
        },
        event_handlers={DocumentUploaded: [AdvanceDocument(queue.enqueue)]},
    )
    return bus, queue


class TestUploadCausesExtraction:
    async def test_uploading_enqueues_and_the_worker_advances_a_stage(self):
        uow_factory = make_in_memory_uow_factory()
        bus, queue = _wire(
            uow_factory,
            InMemoryDocumentStorage(),
            StubDocumentExtractor("# Clean Code"),
        )
        await queue.start(make_pipeline_consumer(bus, uow_factory))

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )
        # Extraction is off the request path: the upload result is still UPLOADED.
        assert document.status is DocumentStatus.UPLOADED

        await queue.join()
        await queue.stop()

        listed = await views.list_documents(uow_factory)
        assert [d.status for d in listed] == [DocumentStatus.EXTRACTED]
