from __future__ import annotations

import re
from urllib.parse import urlparse

import anyio
import httpx
import trafilatura

from cicero.domain.document.ports.article_cover_renderer import (
    ArticleCoverRenderer,
    FetchedArticle,
)


class TrafilaturaArticleCoverRenderer(ArticleCoverRenderer):
    """`ArticleCoverRenderer` over trafilatura + httpx (ADR-028).

    Reads the page's ``og:image`` and byline (author/date) from the HTML trafilatura
    already knows how to parse, then one ``httpx`` GET pulls the image bytes — no
    headless browser. The image URL must be http(s) (an SSRF guard), the response must
    be an image, and it must fit ``max_bytes``; any miss drops the cover to ``None``.
    The byline is returned whether or not a cover is found — best-effort throughout.
    """

    def __init__(
        self,
        *,
        max_bytes: int = 5_000_000,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._timeout = httpx.Timeout(timeout)
        self._transport = transport

    async def fetch_cover(self, url: str) -> FetchedArticle:
        image_url, author, year = await anyio.to_thread.run_sync(self._metadata, url)
        image = await self._download(image_url) if image_url is not None else None
        return FetchedArticle(image=image, author=author, year=year)

    def _metadata(self, url: str) -> tuple[str | None, str | None, int | None]:
        """The page's og:image URL (scheme-guarded), author, and year — one fetch."""
        html = trafilatura.fetch_url(url)
        if not html:
            return None, None, None
        metadata = trafilatura.extract_metadata(html)
        if metadata is None:
            return None, None, None
        image = metadata.image
        if not image or urlparse(image).scheme not in ("http", "https"):
            image = None
        return image, metadata.author or None, _year_from_date(metadata.date)

    async def _download(self, image_url: str) -> bytes | None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, follow_redirects=True
            ) as client:
                response = await client.get(image_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        if not response.headers.get("content-type", "").startswith("image/"):
            return None
        content = response.content
        return content if len(content) <= self._max_bytes else None


def _year_from_date(value: str | None) -> int | None:
    """trafilatura normalises dates to ``YYYY-MM-DD`` — pull the leading year, if any."""
    if not value:
        return None
    match = re.search(r"\d{4}", value)
    return int(match.group()) if match else None
