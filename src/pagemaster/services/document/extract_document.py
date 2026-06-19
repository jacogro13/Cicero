import logging
from collections.abc import Callable

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_id import DocumentId
from pagemaster.domain.document.exceptions import DocumentNotFound
from pagemaster.domain.document.ports.document_extractor import DocumentExtractor
from pagemaster.domain.document.ports.document_storage import DocumentStorage
from pagemaster.domain.ports.unit_of_work import UnitOfWorkFactory

logger = logging.getLogger(__name__)


class ExtractDocument:
    """Use case: extract a document's source to Markdown and advance its status (ADR-009).

    Commits ``PROCESSING`` first (so the in-flight state is observable), then runs
    the heavy I/O outside any transaction. Storage-first like ``UploadDocument``
    (ADR-004): the Markdown blob is written before ``READY`` is committed, so a
    READY document never points at a missing content file. An extraction failure
    marks ``FAILED`` (status is the outcome channel); an unknown id is raised.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        storage: DocumentStorage,
        extractor: DocumentExtractor,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._extractor = extractor

    async def execute(self, document_id: DocumentId) -> None:
        async with self._uow_factory() as uow:
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
            await self._mark(document_id, lambda doc: doc.mark_failed())
            return

        await self._mark(document_id, lambda doc: doc.mark_ready())

    async def _mark(
        self, document_id: DocumentId, transition: Callable[[Document], None]
    ) -> None:
        async with self._uow_factory() as uow:
            document = await uow.documents.find_by_id(document_id)
            transition(document)
            await uow.documents.save(document)
            await uow.commit()
