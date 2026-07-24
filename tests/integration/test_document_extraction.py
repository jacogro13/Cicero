"""The DocumentExtractor port, verified against real PyMuPDF (ADR-009/021).

``PyMuPDFExtractor`` turns PDF bytes into an ordered list of chapters — one per
level-1 bookmark, or a single chapter when the PDF has no table of contents. The
sample PDFs are generated here, so the test carries no binary fixture.
"""

import fitz  # PyMuPDF

from cicero.adapters.extraction.pymupdf import PyMuPDFExtractor


def _make_pdf(pages: list[str], toc: list[list] | None = None) -> bytes:
    doc = fitz.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    if toc is not None:
        doc.set_toc(toc)
    try:
        return doc.tobytes()
    finally:
        doc.close()


class TestPyMuPDFExtractor:
    async def test_splits_into_chapters_at_the_level_1_bookmarks(self):
        pdf = _make_pdf(
            ["Alpha body", "Beta body", "Gamma body"],
            toc=[[1, "Alpha", 1], [1, "Beta", 2]],  # 1-based pages
        )

        chapters = await PyMuPDFExtractor().extract(pdf)

        assert [c.title for c in chapters] == ["Alpha", "Beta"]
        assert "Alpha body" in chapters[0].markdown
        assert "Beta body" not in chapters[0].markdown
        # The trailing page with no bookmark of its own folds into the last chapter.
        assert "Beta body" in chapters[1].markdown
        assert "Gamma body" in chapters[1].markdown

    async def test_a_pdf_without_bookmarks_is_a_single_chapter(self):
        pdf = _make_pdf(["Hello Cicero"])

        chapters = await PyMuPDFExtractor().extract(pdf)

        assert len(chapters) == 1
        assert "Hello Cicero" in chapters[0].markdown
