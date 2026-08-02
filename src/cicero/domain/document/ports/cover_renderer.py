from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedCover:
    """A PDF's rendered cover PNG and its docinfo — ``author``/``year`` ``None``
    when the file omits them (ADR-028)."""

    image: bytes
    author: str | None = None
    year: int | None = None


class CoverRenderer(ABC):
    """Port: render a PDF's cover image and read its docinfo (ADR-028). PDF-only —
    a URL document takes the ``ArticleCoverRenderer`` path."""

    @abstractmethod
    async def render_cover(self, pdf: bytes) -> RenderedCover:
        """Render page 0 of ``pdf`` to a PNG, harvesting docinfo while it is open."""
        ...
