from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedCover:
    """A rendered cover image plus the document metadata harvested alongside it.

    A PDF is opened once for both: page 0 becomes the ``image`` (PNG) and the file's
    own docinfo yields ``author``/``year``, the fallback the model fills over (ADR-028).
    """

    image: bytes
    author: str | None = None
    year: int | None = None


class CoverRenderer(ABC):
    """Port: render a PDF's cover image and read its docinfo (ADR-028).

    Cover rendering is PDF-only — the URL branch has no page to render and takes the
    ``ArticleCoverRenderer`` path instead. Concrete adapter: ``PyMuPDFCoverRenderer``.
    """

    @abstractmethod
    async def render_cover(self, pdf: bytes) -> RenderedCover:
        """Render page 0 of ``pdf`` to a PNG, harvesting docinfo while it is open."""
        ...
