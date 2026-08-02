from abc import ABC, abstractmethod

from cicero.domain.document.chapter import Chapter


class ArticleExtractor(ABC):
    """Port: fetch a web page and parse it into one article chapter (ADR-027)."""

    @abstractmethod
    async def extract(self, url: str) -> Chapter:
        """Fetch ``url`` and return its article as one chapter; raises on a failed
        fetch or empty extraction."""
        ...
