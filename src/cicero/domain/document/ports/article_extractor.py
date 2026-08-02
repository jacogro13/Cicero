from abc import ABC, abstractmethod

from cicero.domain.document.chapter import Chapter
from cicero.domain.document.exceptions import ArticleExtractionFailed


class ArticleExtractor(ABC):
    """Port: fetch a web page and parse it into one article chapter (ADR-027)."""

    @abstractmethod
    async def extract(self, url: str) -> Chapter:
        """Fetch ``url`` and return its article as one chapter.

        :raises ArticleExtractionFailed: the fetch failed or the page held no article
            text. Named here rather than in each adapter, so callers depend on the
            port for its failures as they do for its result (ADR-008).
        """
        ...


__all__ = ["ArticleExtractionFailed", "ArticleExtractor"]
