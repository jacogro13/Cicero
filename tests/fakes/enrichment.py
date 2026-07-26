"""In-memory doubles for the enrichment ports (ADR-028) — canned covers and
metadata that record what they were handed, without PyMuPDF, the network, or an LLM.
"""

from __future__ import annotations

from cicero.domain.document.ports.article_cover_renderer import ArticleCoverRenderer
from cicero.domain.document.ports.cover_renderer import CoverRenderer, RenderedCover
from cicero.domain.document.ports.metadata_inferer import InferredMetadata, MetadataInferer


class StubCoverRenderer(CoverRenderer):
    def __init__(
        self, cover: RenderedCover | None = None, error: Exception | None = None
    ) -> None:
        self._cover = cover if cover is not None else RenderedCover(image=b"PNGCOVER")
        self._error = error
        self.received: bytes | None = None

    async def render_cover(self, pdf: bytes) -> RenderedCover:
        self.received = pdf
        if self._error is not None:
            raise self._error
        return self._cover


class StubArticleCoverRenderer(ArticleCoverRenderer):
    def __init__(self, cover: bytes | None = b"OGIMAGE") -> None:
        self._cover = cover
        self.received: str | None = None

    async def fetch_cover(self, url: str) -> bytes | None:
        self.received = url
        return self._cover


class StubMetadataInferer(MetadataInferer):
    def __init__(
        self, metadata: InferredMetadata | None = None, error: Exception | None = None
    ) -> None:
        self._metadata = metadata if metadata is not None else InferredMetadata()
        self._error = error
        self.received: str | None = None

    async def infer(self, text: str) -> InferredMetadata:
        self.received = text
        if self._error is not None:
            raise self._error
        return self._metadata
