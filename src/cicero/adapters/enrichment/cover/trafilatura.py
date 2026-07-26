from __future__ import annotations

from urllib.parse import urlparse

import anyio
import httpx
import trafilatura

from cicero.domain.document.ports.article_cover_renderer import ArticleCoverRenderer


class TrafilaturaArticleCoverRenderer(ArticleCoverRenderer):
    """`ArticleCoverRenderer` over trafilatura + httpx (ADR-028).

    Reads the page's ``og:image`` from the HTML trafilatura already knows how to
    parse, then one ``httpx`` GET pulls the bytes — no headless browser. The image
    URL must be http(s) (an SSRF guard), the response must be an image, and it must
    fit ``max_bytes``; any miss returns ``None``, since the cover is best-effort.
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

    async def fetch_cover(self, url: str) -> bytes | None:
        image_url = await anyio.to_thread.run_sync(self._og_image, url)
        if image_url is None:
            return None
        return await self._download(image_url)

    def _og_image(self, url: str) -> str | None:
        html = trafilatura.fetch_url(url)
        if not html:
            return None
        metadata = trafilatura.extract_metadata(html)
        image = metadata.image if metadata else None
        if not image or urlparse(image).scheme not in ("http", "https"):
            return None
        return image

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
