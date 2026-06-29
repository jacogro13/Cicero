from __future__ import annotations

import anyio
import fitz  # PyMuPDF
import pymupdf4llm

from cicero.domain.document.ports.document_extractor import DocumentExtractor


class PyMuPDFExtractor(DocumentExtractor):
    """`DocumentExtractor` backed by PyMuPDF, in-process (ADR-009).

    ``pymupdf4llm`` renders a PDF to Markdown. The library is synchronous and
    CPU-bound, so each extraction is offloaded to the anyio worker thread to keep
    the event loop free (ADR-007). Heading hierarchy from the PDF's TOC is a later
    slice; this yields flat Markdown.
    """

    async def extract_markdown(self, data: bytes) -> str:
        return await anyio.to_thread.run_sync(self._extract, data)

    def _extract(self, data: bytes) -> str:
        document = fitz.open(stream=data, filetype="pdf")
        try:
            return pymupdf4llm.to_markdown(document, show_progress=False)
        finally:
            document.close()
