from __future__ import annotations

import logging

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.ports.article_cover_renderer import ArticleCoverRenderer
from cicero.domain.document.ports.cover_renderer import CoverRenderer
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.document.ports.metadata_inferer import MetadataInferer
from cicero.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class EnrichDocument:
    """Handler for ``EnrichDocument``: fill a document's cover, authors, and year,
    driving PENDING/ENRICHING→ENRICHED/FAILED on the enrichment branch (ADR-028).

    Best-effort and off the readability spine: it never touches ``status``, so a
    failure leaves the document exactly as readable as before. A stale intent for a
    deleted document is dropped, not raised — the branch never fails past the worker.

    The cover is chosen by ``source_url`` (mirroring extraction, ADR-027): a URL
    document's cover is its ``og:image``, a blob document's is its rendered first
    page — which also yields the docinfo the model's metadata falls back to.
    """

    def __init__(
        self,
        storage: DocumentStorage,
        cover_renderer: CoverRenderer,
        article_cover_renderer: ArticleCoverRenderer,
        metadata_inferer: MetadataInferer,
    ) -> None:
        self._storage = storage
        self._cover_renderer = cover_renderer
        self._article_cover_renderer = article_cover_renderer
        self._metadata_inferer = metadata_inferer

    async def __call__(self, command: commands.EnrichDocument, uow: UnitOfWork) -> None:
        document_id = command.document_id
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Deleted before enrichment; dropping id=%s", document_id)
                return
            document.mark_enriching()
            await uow.documents.save(document)
            await uow.commit()

        try:
            cover, authors, year = await self._collect(document)
        except Exception:
            logger.exception("Enrichment failed id=%s", document_id)
            await self._mark_failed(document_id, uow)
            return

        # Deleted while we worked? Dropping a stale stage is not an error (ADR-014),
        # and bailing before the put leaves no orphan cover blob.
        if not await self._still_present(document_id, uow):
            return

        if cover is not None:
            await self._storage.put(document.cover_key, cover)

        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                logger.info("Deleted during enrichment; dropping id=%s", document_id)
                return
            document.apply_enrichment(authors=authors, year=year, has_cover=cover is not None)
            document.mark_enriched()
            await uow.documents.save(document)
            await uow.commit()

    async def _collect(
        self, document: Document
    ) -> tuple[bytes | None, str | None, int | None]:
        """The cover bytes (or ``None``) and the merged authors/year. The model's
        inference wins; a PDF's own docinfo fills whatever it leaves blank."""
        opening = (await self._storage.get(document.chapter_key(0))).decode()
        metadata = await self._metadata_inferer.infer(opening)
        if document.source_url is not None:
            cover = await self._article_cover_renderer.fetch_cover(document.source_url)
            author_fallback = year_fallback = None
        else:
            rendered = await self._cover_renderer.render_cover(
                await self._storage.get(document.source_key)
            )
            cover, author_fallback, year_fallback = (
                rendered.image,
                rendered.author,
                rendered.year,
            )
        return cover, metadata.authors or author_fallback, metadata.year or year_fallback

    async def _still_present(self, document_id: DocumentId, uow: UnitOfWork) -> bool:
        async with uow:
            present = await uow.documents.find_by_id(document_id) is not None
        if not present:
            logger.info("Document deleted during enrichment; dropping id=%s", document_id)
        return present

    async def _mark_failed(self, document_id: DocumentId, uow: UnitOfWork) -> None:
        async with uow:
            document = await uow.documents.find_by_id(document_id)
            if document is None:
                return
            document.mark_enrichment_failed()
            await uow.documents.save(document)
            await uow.commit()
