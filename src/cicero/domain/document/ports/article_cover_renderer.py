from abc import ABC, abstractmethod


class ArticleCoverRenderer(ABC):
    """Port: fetch a web article's cover image (ADR-028).

    The URL branch's counterpart to ``CoverRenderer``: an article has no page to
    render, so its cover is the page's ``og:image`` — fetched, not rendered, and
    ``None`` when the page ships none. Concrete adapter:
    ``TrafilaturaArticleCoverRenderer``.
    """

    @abstractmethod
    async def fetch_cover(self, url: str) -> bytes | None:
        """Return the article's ``og:image`` bytes, or ``None`` if it has none or
        cannot be fetched — best-effort, never raising past the caller."""
        ...
