from __future__ import annotations

import re

import anyio
import fitz  # PyMuPDF

from cicero.domain.document.ports.cover_renderer import CoverRenderer, RenderedCover

# ~144 dpi — a crisp thumbnail without carrying a full-resolution page.
_COVER_SCALE = fitz.Matrix(2, 2)


class PyMuPDFCoverRenderer(CoverRenderer):
    """`CoverRenderer` backed by PyMuPDF, in-process (ADR-028).

    Opens the PDF once: page 0 is rasterised to a PNG and the file's docinfo yields
    author/year. Synchronous and CPU-bound, so offloaded to a worker thread (ADR-007).
    """

    async def render_cover(self, pdf: bytes) -> RenderedCover:
        return await anyio.to_thread.run_sync(self._render, pdf)

    def _render(self, pdf: bytes) -> RenderedCover:
        document = fitz.open(stream=pdf, filetype="pdf")
        try:
            image = document[0].get_pixmap(matrix=_COVER_SCALE).tobytes("png")
            info = document.metadata or {}
            return RenderedCover(
                image=image,
                author=info.get("author") or None,
                year=_year_from_pdf_date(info.get("creationDate")),
            )
        finally:
            document.close()


def _year_from_pdf_date(value: str | None) -> int | None:
    """PDF dates look like ``D:YYYYMMDD...`` — pull the leading 4-digit year, if any."""
    if not value:
        return None
    match = re.search(r"\d{4}", value)
    return int(match.group()) if match else None
