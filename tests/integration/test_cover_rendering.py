"""The CoverRenderer port, verified against real PyMuPDF (ADR-028).

``PyMuPDFCoverRenderer`` renders a PDF's first page to a PNG and harvests the
file's docinfo (author, year) in the same open — the fallback the model fills over.
The sample PDFs are generated here, so the test carries no binary fixture.
"""

import fitz  # PyMuPDF

from cicero.adapters.enrichment.cover.pymupdf import PyMuPDFCoverRenderer

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_pdf(*, author: str | None = None, creation: str | None = None) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Cover Page")
    info = {}
    if author is not None:
        info["author"] = author
    if creation is not None:
        info["creationDate"] = creation
    if info:
        doc.set_metadata(info)
    try:
        return doc.tobytes()
    finally:
        doc.close()


class TestPyMuPDFCoverRenderer:
    async def test_renders_the_first_page_as_png(self):
        cover = await PyMuPDFCoverRenderer().render_cover(_make_pdf())

        assert cover.image[:8] == _PNG_MAGIC

    async def test_harvests_author_and_year_from_docinfo(self):
        pdf = _make_pdf(author="Jane Doe", creation="D:20030115000000")

        cover = await PyMuPDFCoverRenderer().render_cover(pdf)

        assert cover.author == "Jane Doe"
        assert cover.year == 2003

    async def test_missing_docinfo_leaves_author_and_year_none(self):
        # PyMuPDF reports empty docinfo as "" — the adapter normalises that to None.
        cover = await PyMuPDFCoverRenderer().render_cover(_make_pdf())

        assert cover.author is None
        assert cover.year is None
