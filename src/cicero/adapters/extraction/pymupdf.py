from __future__ import annotations

import anyio
import fitz  # PyMuPDF
import pymupdf4llm

from cicero.domain.document.ports.document_extractor import DocumentExtractor


class PyMuPDFExtractor(DocumentExtractor):
    """`DocumentExtractor` backed by PyMuPDF, in-process (ADR-009).

    ``pymupdf4llm`` renders a PDF to Markdown; the call is synchronous and CPU-bound,
    so it is offloaded to an anyio worker thread (ADR-007).
    """

    async def extract_markdown(self, data: bytes) -> str:
        return await anyio.to_thread.run_sync(self._extract, data)

    def _extract(self, data: bytes) -> str:
        document = fitz.open(stream=data, filetype="pdf")
        try:
            return pymupdf4llm.to_markdown(document, show_progress=False)
        finally:
            document.close()
