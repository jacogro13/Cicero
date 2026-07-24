import logging
from collections.abc import Callable

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_extractor import DocumentExtractor
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class ExtractDocument:
    """Handler for ``ExtractDocument``: extract the source into chapters, driving
    EXTRACTING→EXTRACTED/FAILED (ADR-009/021). Each chapter's Markdown is stored at
    its chapter key and the ordered titles via ``uow.chapters``. Raises
    ``DocumentNotFound`` for an unknown id.
    """

    def __init__(self, storage: DocumentStorage, extractor: DocumentExtractor) -> None:
        self._storage = storage
        self._extractor = extractor

    async def __call__(self, command: commands.ExtractDocument, uow: UnitOfWork) -> None:
        document_id = command.document_id
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            document.mark_extracting()
            await uow.documents.save(document)
            await uow.commit()

        try:
            source = await self._storage.get(document.source_key)
            chapters = await self._extractor.extract(source)
            # Storage-first (ADR-004): the blobs land before EXTRACTED commits, so an
            # EXTRACTED document never points at a missing chapter.
            for index, chapter in enumerate(chapters):
                await self._storage.put(document.chapter_key(index), chapter.markdown.encode())
        except Exception:
            logger.exception("Extraction failed id=%s", document_id)
            await self._mark(document_id, uow, lambda doc: doc.mark_failed())
            return

        titles = [chapter.title for chapter in chapters]
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            await uow.chapters.save(document_id, titles)
            document.mark_extracted()
            await uow.documents.save(document)
            await uow.commit()

    async def _mark(
        self,
        document_id: DocumentId,
        uow: UnitOfWork,
        transition: Callable[[Document], None],
    ) -> None:
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            transition(document)
            await uow.documents.save(document)
            await uow.commit()
