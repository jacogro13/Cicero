import logging

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.document.ports.document_summarizer import DocumentSummarizer
from cicero.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class SummariseDocument:
    """Handler for ``SummariseDocument``: summarise each chapter from its stored
    Markdown, driving SUMMARISING→SUMMARISED/FAILED (ADR-016/021). Each summary
    commits as it is produced, so a re-run resumes rather than re-pays (ADR-031).
    Raises ``DocumentNotFound``."""

    def __init__(self, storage: DocumentStorage, summarizer: DocumentSummarizer) -> None:
        self._storage = storage
        self._summarizer = summarizer

    async def __call__(self, command: commands.SummariseDocument, uow: UnitOfWork) -> None:
        document_id = command.document_id
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            document.mark_summarising()
            await uow.documents.save(document)
            chapter_count = len(await uow.chapters.list(document_id))
            await uow.commit()

        try:
            summarised = await self._summarise_chapters(document, chapter_count, uow)
        except Exception:
            logger.exception("Summarization failed id=%s", document_id)
            await self._mark_failed(document_id, uow)
            return

        # Deleted mid-summarisation? Dropping a stale stage is not an error (ADR-014).
        if not summarised:
            logger.info("Document deleted during summarisation; dropping id=%s", document_id)
            return

        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Document deleted during summarisation; dropping id=%s", document_id)
                return
            document.mark_summarised()
            await uow.documents.save(document)
            await uow.commit()

    async def _summarise_chapters(
        self, document: Document, count: int, uow: UnitOfWork
    ) -> bool:
        """Summarise and persist every chapter still missing one, committing each as it
        is produced (ADR-031). ``False`` if the document was deleted partway — the call
        already in flight is still paid in full, and its result dropped (ADR-023)."""
        async with uow:
            if await uow.documents.find_by_id(document.id) is None:
                return False
            # Chapters a previous run already paid for are not bought again (ADR-031).
            done = await uow.summaries.all(document.id)
        for index in range(count):
            if index in done:
                continue
            markdown = (await self._storage.get(document.chapter_key(index))).decode()
            summary = await self._summarizer.summarize(markdown)
            # The transaction that saves a summary is also the deletion checkpoint
            # before the *next* chapter's call: one round trip, both jobs.
            async with uow:
                if await uow.documents.find_by_id(document.id) is None:
                    return False
                await uow.summaries.save(document.id, index, summary)
                await uow.commit()
        return True

    async def _mark_failed(self, document_id: DocumentId, uow: UnitOfWork) -> None:
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Document deleted during summarisation; dropping id=%s", document_id)
                return
            document.mark_failed()
            await uow.documents.save(document)
            await uow.commit()
