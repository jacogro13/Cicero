"""Upload *causes* extraction, off the request path and driven by status (ADR-012/013/014).

An upload raises ``DocumentUploaded``; ``AdvanceDocument`` puts the document id on the
job queue and the upload returns immediately as UPLOADED. The worker then reads the
document's persisted status back and issues the command that status calls for — so
draining the queue advances the pipeline without the upload ever having blocked, and
without any handler naming a verb.
"""

from cicero.domain.document import commands
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.events import DocumentUploaded, ExtractionCompleted
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.pipeline import make_pipeline_consumer
from cicero.services.document.advance_document import AdvanceDocument
from cicero.services import views
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.summarise_document import SummariseDocument
from cicero.services.document.upload_document import UploadDocument
from cicero.services.messagebus import MessageBus

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    StubDocumentSummarizer,
    make_in_memory_uow_factory,
)


def _wire(uow_factory, storage, extractor, summarizer) -> tuple[MessageBus, JobQueue]:
    """The full handler/queue wiring the composition root builds (ADR-011/012/013/014/016).

    Both slow stages subscribe the *same* ``AdvanceDocument`` to their completion event,
    so extraction completing re-enqueues the document and the edge derives the next
    command (summarization) from its status — one subscription is the whole cost.
    """
    queue = JobQueue()
    bus = MessageBus(
        uow_factory,
        command_handlers={
            commands.UploadDocument: UploadDocument(storage),
            commands.DeleteDocument: DeleteDocument(storage),
            commands.ExtractDocument: ExtractDocument(storage, extractor),
            commands.SummariseDocument: SummariseDocument(storage, summarizer),
        },
        event_handlers={
            DocumentUploaded: [AdvanceDocument(queue.enqueue)],
            ExtractionCompleted: [AdvanceDocument(queue.enqueue)],
        },
    )
    return bus, queue


class TestUploadRunsThePipeline:
    async def test_uploading_drives_the_document_all_the_way_to_summarised(self):
        uow_factory = make_in_memory_uow_factory()
        bus, queue = _wire(
            uow_factory,
            InMemoryDocumentStorage(),
            StubDocumentExtractor("# Clean Code"),
            StubDocumentSummarizer("A crisp summary."),
        )
        await queue.start(make_pipeline_consumer(bus, uow_factory))

        document = await bus.handle(
            commands.UploadDocument(title="Clean Code", content=b"%PDF-1.4 bytes")
        )
        # The stages are off the request path: the upload result is still UPLOADED.
        assert document.status is DocumentStatus.UPLOADED

        await queue.join()
        await queue.stop()

        listed = await views.list_documents(uow_factory)
        assert [d.status for d in listed] == [DocumentStatus.SUMMARISED]
        summary = await views.get_document_summary(uow_factory, document.id)
        assert summary.text == "A crisp summary."
