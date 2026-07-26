"""The ArticleExtractor port, verified against real trafilatura (ADR-027).

``TrafilaturaArticleExtractor`` fetches a page and reduces it to one article chapter
— title from the page metadata, body as Markdown. Only the network fetch is stubbed;
the parsing is real, mirroring the PyMuPDF extractor's real-library integration test.
The HTML is inline, so the test carries no fixture and needs no container.
"""

import trafilatura

from cicero.adapters.extraction.trafilatura import TrafilaturaArticleExtractor

_HTML = """<html><head><title>Clean Architecture</title></head>
<body><article><h1>Clean Architecture</h1>
<p>A clean architecture separates the concerns of a system into concentric layers,
with dependencies pointing only inward toward the domain.</p>
<p>Frameworks and drivers sit on the outside; the business rules at the core know
nothing of them, which keeps the core testable and durable.</p>
</article></body></html>"""


async def test_parses_a_real_page_into_a_titled_chapter(monkeypatch):
    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: _HTML)

    chapter = await TrafilaturaArticleExtractor().extract("https://example.com/a")

    assert chapter.title == "Clean Architecture"
    assert "concentric layers" in chapter.markdown
