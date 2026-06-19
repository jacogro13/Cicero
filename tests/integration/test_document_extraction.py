"""The DocumentExtractor port, verified against real PyMuPDF (ADR-009).

``PyMuPDFExtractor`` turns PDF bytes into Markdown in-process — the real library
path the in-memory stub stands in for. The sample PDF is generated here, so the
test carries no binary fixture.
"""

import fitz  # PyMuPDF

from pagemaster.adapters.extraction.pymupdf import PyMuPDFExtractor


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    try:
        return doc.tobytes()
    finally:
        doc.close()


class TestPyMuPDFExtractor:
    async def test_extracts_the_pdf_text_as_markdown(self):
        pdf = _make_pdf("Hello PageMaster")

        markdown = await PyMuPDFExtractor().extract_markdown(pdf)

        assert "Hello PageMaster" in markdown
