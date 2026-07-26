from abc import ABC, abstractmethod

from cicero.domain.document.chapter import Chapter


class ArticleExtractor(ABC):
    """Port: fetch a web page and parse it into one article chapter (ADR-027).

    The URL source's counterpart to ``DocumentExtractor``: a URL document has no
    blob, so its source is the link, fetched and reduced to a single ``Chapter``
    (the article title + Markdown body). Concrete adapter:
    ``TrafilaturaArticleExtractor``.
    """

    @abstractmethod
    async def extract(self, url: str) -> Chapter:
        """Fetch ``url`` and return its article as one chapter; raise on a failed
        fetch or empty extraction so the stage can fail the document."""
        ...
