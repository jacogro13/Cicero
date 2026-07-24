from __future__ import annotations

import anyio
import fitz  # PyMuPDF
import pymupdf4llm

from cicero.domain.document.chapter import Chapter
from cicero.domain.document.chapterization import chapter_ranges
from cicero.domain.document.ports.document_extractor import DocumentExtractor


class PyMuPDFExtractor(DocumentExtractor):
    """`DocumentExtractor` backed by PyMuPDF, in-process (ADR-009/021).

    Chapter boundaries come from the PDF's own bookmarks (``get_toc()``, mapped by
    the pure ``chapter_ranges``); ``pymupdf4llm`` renders each chapter's page range
    to Markdown. The call is synchronous and CPU-bound, so it is offloaded to an
    anyio worker thread (ADR-007).
    """

    async def extract(self, data: bytes) -> list[Chapter]:
        return await anyio.to_thread.run_sync(self._extract, data)

    def _extract(self, data: bytes) -> list[Chapter]:
        document = fitz.open(stream=data, filetype="pdf")
        try:
            ranges = chapter_ranges(document.get_toc(), document.page_count)
            return [
                Chapter(
                    title=chapter.title,
                    markdown=pymupdf4llm.to_markdown(
                        document,
                        pages=list(range(chapter.first_page, chapter.last_page + 1)),
                        show_progress=False,
                    ),
                )
                for chapter in ranges
            ]
        finally:
            document.close()
