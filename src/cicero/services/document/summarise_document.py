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
    """Handler for ``SummariseDocument``: summarise the extracted text and persist it
    as a read model, driving SUMMARISING→SUMMARISED/FAILED (ADR-016). The chapters are
    read from storage and joined; the summary is written in the same transaction as
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
            markdown = await self._read_chapters(document, chapter_count)
            summary = await self._summarizer.summarize(markdown)
        except Exception:
            logger.exception("Summarization failed id=%s", document_id)
            await self._mark_failed(document_id, uow)
            return

        async with uow:
            document = await uow.documents.find_by_id(document_id)
            document.mark_summarised()
            await uow.documents.save(document)
            await uow.summaries.save(document_id, summary)
            await uow.commit()

    async def _read_chapters(self, document: Document, count: int) -> str:
        """The document's chapter Markdown, in order, joined into one string."""
        parts = [
            (await self._storage.get(document.chapter_key(index))).decode()
            for index in range(count)
        ]
        return "\n\n".join(parts)

    async def _mark_failed(self, document_id: DocumentId, uow: UnitOfWork) -> None:
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            document.mark_failed()
            await uow.documents.save(document)
            await uow.commit()
