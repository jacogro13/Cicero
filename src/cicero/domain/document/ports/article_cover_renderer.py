from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedArticle:
    """A web article's cover image and byline, from one page fetch — any field
    ``None`` when the page omits it (ADR-028)."""

    image: bytes | None = None
    author: str | None = None
    year: int | None = None


class ArticleCoverRenderer(ABC):
    """Port: fetch a web article's cover image and byline (ADR-028)."""

    @abstractmethod
    async def fetch_cover(self, url: str) -> FetchedArticle:
        """Fetch the page once; best-effort, so a missing cover is ``None``, not an error."""
        ...
