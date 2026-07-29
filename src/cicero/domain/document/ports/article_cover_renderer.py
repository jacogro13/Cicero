from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedArticle:
    """An article's cover image plus the byline harvested from the same fetch.

    The URL branch's counterpart to ``RenderedCover``: one page fetch yields the
    ``og:image`` (``None`` when the page ships none) and the structured metadata's
    ``author``/``year`` — for a URL these are the *primary* source, the model filling
    only what they omit (ADR-028 amendment).
    """

    image: bytes | None = None
    author: str | None = None
    year: int | None = None


class ArticleCoverRenderer(ABC):
    """Port: fetch a web article's cover image and byline (ADR-028).

    An article has no page to render, so its cover is the page's ``og:image`` —
    fetched, not rendered — and its author/year come from the structured metadata
    parsed alongside. Concrete adapter: ``TrafilaturaArticleCoverRenderer``.
    """

    @abstractmethod
    async def fetch_cover(self, url: str) -> FetchedArticle:
        """Fetch the page once, returning its cover bytes and byline — any field
        ``None`` when the page omits it — best-effort, never raising past the caller."""
        ...
