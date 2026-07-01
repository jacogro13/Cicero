import logging
from collections.abc import Callable

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentUploaded
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.document.ports.document_extractor import DocumentExtractor
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class ExtractDocument:
    """Handler for ``DocumentUploaded``: extract the source to Markdown, driving
    PROCESSING→READY/FAILED (ADR-009). An internal reaction, not a command (ADR-012);
    storage-first (ADR-004). Raises ``DocumentNotFound`` for an unknown id.
    """

    def __init__(self, storage: DocumentStorage, extractor: DocumentExtractor) -> None:
        self._storage = storage
        self._extractor = extractor

    async def __call__(self, event: DocumentUploaded, uow: UnitOfWork) -> None:
        document_id = event.document_id
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            document.mark_processing()
            await uow.documents.save(document)
            await uow.commit()

        try:
            source = await self._storage.get(document.source_key)
            markdown = await self._extractor.extract_markdown(source)
            await self._storage.put(document.content_key, markdown.encode())
        except Exception:
            logger.exception("Extraction failed id=%s", document_id)
            await self._mark(document_id, uow, lambda doc: doc.mark_failed())
            return

        await self._mark(document_id, uow, lambda doc: doc.mark_ready())

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
