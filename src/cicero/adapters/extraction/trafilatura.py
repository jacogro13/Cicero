from __future__ import annotations

import anyio
import trafilatura

from cicero.domain.document.chapter import Chapter
from cicero.domain.document.ports.article_extractor import ArticleExtractor


class ArticleExtractionError(Exception):
    """The page could not be fetched or yielded no article text (ADR-027)."""


class TrafilaturaArticleExtractor(ArticleExtractor):
    """`ArticleExtractor` backed by trafilatura (ADR-027).

    Fetches the page, extracts the main body as Markdown, and reads the title from
    the page metadata (falling back to the URL). Fetch + parse are synchronous and
    network/CPU-bound, so they run on an anyio worker thread (ADR-007).
    """

    async def extract(self, url: str) -> Chapter:
        return await anyio.to_thread.run_sync(self._extract, url)

    def _extract(self, url: str) -> Chapter:
        html = trafilatura.fetch_url(url)
        if html is None:
            raise ArticleExtractionError(f"could not fetch {url!r}")
        markdown = trafilatura.extract(html, output_format="markdown", with_metadata=False)
        if not markdown:
            raise ArticleExtractionError(f"no article text at {url!r}")
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else url
        return Chapter(title=title, markdown=markdown)
