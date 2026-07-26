import logging
from collections.abc import Callable

from cicero.domain.document import commands
from cicero.domain.document.chapter import Chapter
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.article_extractor import ArticleExtractor
from cicero.domain.document.ports.document_extractor import DocumentExtractor
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class ExtractDocument:
    """Handler for ``ExtractDocument``: extract the source into chapters, driving
    EXTRACTING→EXTRACTED/FAILED (ADR-009/021/027). Each chapter's Markdown is stored
    at its chapter key and the ordered titles via ``uow.chapters``. Raises
    ``DocumentNotFound`` for an unknown id.

    The source is chosen by ``source_url`` — a URL document is fetched and parsed as
    one article chapter, a blob document PyMuPDF-extracted into TOC chapters — never
    by ``kind``, which stays a browsing label (ADR-026/027).
    """

    def __init__(
        self,
        storage: DocumentStorage,
        extractor: DocumentExtractor,
        article_extractor: ArticleExtractor,
    ) -> None:
        self._storage = storage
        self._extractor = extractor
        self._article_extractor = article_extractor

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
            chapters = await self._extract_source(document)
        except Exception:
            logger.exception("Extraction failed id=%s", document_id)
            await self._mark(document_id, uow, lambda doc: doc.mark_failed())
            return

        # Deleted while we extracted? Dropping a stale stage is not an error (ADR-014).
        # Bail before writing any chapter blob, so a deleted document leaves no orphans.
        if not await self._still_present(document_id, uow):
            return

        # Storage-first (ADR-004): the blobs land before EXTRACTED commits, so an
        # EXTRACTED document never points at a missing chapter.
        for index, chapter in enumerate(chapters):
            await self._storage.put(document.chapter_key(index), chapter.markdown.encode())

        titles = [chapter.title for chapter in chapters]
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Document deleted during extraction; dropping id=%s", document_id)
                return
            await uow.chapters.save(document_id, titles)
            document.mark_extracted()
            await uow.documents.save(document)
            await uow.commit()

    async def _extract_source(self, document: Document) -> list[Chapter]:
        """A URL document is one fetched article chapter; a blob document its TOC
        chapters. Branch on the source, not on kind (ADR-026/027)."""
        if document.source_url is not None:
            return [await self._article_extractor.extract(document.source_url)]
        source = await self._storage.get(document.source_key)
        return await self._extractor.extract(source)

    async def _still_present(self, document_id: DocumentId, uow: UnitOfWork) -> bool:
        async with uow:
            present = await uow.documents.find_by_id(document_id) is not None
        if not present:
            logger.info("Document deleted during extraction; dropping id=%s", document_id)
        return present

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
