"""`TrafilaturaArticleExtractor` adapter logic (ADR-027).

trafilatura's three calls are stubbed so these isolate the adapter's own decisions —
the title-or-URL fallback and the fetch/empty guards — not trafilatura's extraction
quality (that is covered for real in tests/integration/test_article_extraction.py).
"""

from types import SimpleNamespace

import pytest
import trafilatura

from cicero.adapters.extraction.trafilatura import TrafilaturaArticleExtractor
from cicero.domain.document.exceptions import ArticleExtractionFailed


def _stub(monkeypatch, *, html="<html></html>", markdown="# T\n\nBody.", title="Real Title"):
    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: html)
    monkeypatch.setattr(trafilatura, "extract", lambda *a, **k: markdown)
    metadata = None if title is None else SimpleNamespace(title=title)
    monkeypatch.setattr(trafilatura, "extract_metadata", lambda html: metadata)


class TestTrafilaturaArticleExtractor:
    async def test_wraps_the_body_and_metadata_title_into_a_chapter(self, monkeypatch):
        _stub(monkeypatch, markdown="# T\n\nBody.", title="Real Title")

        chapter = await TrafilaturaArticleExtractor().extract("https://example.com/a")

        assert chapter.title == "Real Title"
        assert chapter.markdown == "# T\n\nBody."

    async def test_title_falls_back_to_the_url_when_metadata_has_none(self, monkeypatch):
        _stub(monkeypatch, title=None)

        chapter = await TrafilaturaArticleExtractor().extract("https://example.com/a")

        assert chapter.title == "https://example.com/a"

    async def test_a_failed_fetch_raises(self, monkeypatch):
        # trafilatura returns None when the page can't be fetched. The type raised is
        # the port's own, declared in the domain, so a caller in services/ can name it
        # without importing this adapter (ADR-001/008); the stage turns it into FAILED.
        _stub(monkeypatch, html=None)

        with pytest.raises(ArticleExtractionFailed):
            await TrafilaturaArticleExtractor().extract("https://example.com/missing")

    async def test_empty_extraction_raises(self, monkeypatch):
        # A fetched page trafilatura finds no article text in is a failure, not an
        # empty document.
        _stub(monkeypatch, markdown=None)

        with pytest.raises(ArticleExtractionFailed):
            await TrafilaturaArticleExtractor().extract("https://example.com/empty")
