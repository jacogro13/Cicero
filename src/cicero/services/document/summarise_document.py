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
    """Handler for ``SummariseDocument``: summarise each chapter from its own stored
    Markdown and persist the results as a read model, driving SUMMARISING→SUMMARISED/
    FAILED (ADR-016/021). The summaries are written in the same transaction as
    ``mark_summarised``. Raises ``DocumentNotFound``.
    """

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
            summaries = await self._summarise_chapters(document, chapter_count, uow)
        except Exception:
            logger.exception("Summarization failed id=%s", document_id)
            await self._mark_failed(document_id, uow)
            return

        # Deleted mid-summarisation? Dropping a stale stage is not an error (ADR-014).
        if summaries is None:
            logger.info("Document deleted during summarisation; dropping id=%s", document_id)
            return

        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Document deleted during summarisation; dropping id=%s", document_id)
                return
            document.mark_summarised()
            await uow.documents.save(document)
            for index, summary in enumerate(summaries):
                await uow.summaries.save(document_id, index, summary)
            await uow.commit()

    async def _summarise_chapters(
        self, document: Document, count: int, uow: UnitOfWork
    ) -> list[str] | None:
        """Summarise each chapter from its own stored Markdown, in order. Returns
        ``None`` if the document was deleted partway, so no further chapter is
        summarised — the call already in flight is still paid in full (ADR-023)."""
        summaries: list[str] = []
        for index in range(count):
            async with uow:
                if await uow.documents.find_by_id(document.id) is None:
                    return None
            markdown = (await self._storage.get(document.chapter_key(index))).decode()
            summaries.append(await self._summarizer.summarize(markdown))
        return summaries

    async def _mark_failed(self, document_id: DocumentId, uow: UnitOfWork) -> None:
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Document deleted during summarisation; dropping id=%s", document_id)
                return
            document.mark_failed()
            await uow.documents.save(document)
            await uow.commit()
