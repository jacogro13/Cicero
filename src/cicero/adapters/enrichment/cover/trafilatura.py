from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

import anyio
import httpx
import trafilatura

from cicero.adapters.http.retry import DEFAULT_RETRY, RetryPolicy, with_retry
from cicero.domain.document.ports.article_cover_renderer import (
    ArticleCoverRenderer,
    FetchedArticle,
)

_MAX_REDIRECTS = 3


class TrafilaturaArticleCoverRenderer(ArticleCoverRenderer):
    """`ArticleCoverRenderer` over trafilatura + httpx (ADR-028).

    Reads the page's ``og:image`` and byline (author/date) from the HTML trafilatura
    already knows how to parse, then one ``httpx`` GET pulls the image bytes — no
    headless browser. The response must be an image and must fit ``max_bytes``; any
    miss drops the cover to ``None``. The byline is returned whether or not a cover is
    found — best-effort throughout.

    The image URL is chosen by the fetched page, not by the operator, so it is fetched
    only if every address it resolves to is public — or is one the requested page itself
    resolved to, since naming an internal page implies consent to its own images.
    Redirects are followed manually so the check applies to every hop.
    """

    def __init__(
        self,
        *,
        max_bytes: int = 5_000_000,
        timeout: float = 15.0,
        retry: RetryPolicy = DEFAULT_RETRY,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._timeout = httpx.Timeout(timeout)
        self._retry = retry
        self._transport = transport

    async def fetch_cover(self, url: str) -> FetchedArticle:
        image_url, author, year = await anyio.to_thread.run_sync(self._metadata, url)
        image = None
        if image_url is not None:
            # Whatever the operator's own URL points at, they have already asked for.
            allowed = await anyio.to_thread.run_sync(_resolve, url)
            image = await self._download(image_url, allowed=allowed)
        return FetchedArticle(image=image, author=author, year=year)

    def _metadata(self, url: str) -> tuple[str | None, str | None, int | None]:
        """The page's og:image URL, author, and year — one fetch."""
        html = trafilatura.fetch_url(url)
        if not html:
            return None, None, None
        metadata = trafilatura.extract_metadata(html)
        if metadata is None:
            return None, None, None
        return metadata.image or None, metadata.author or None, _year_from_date(metadata.date)

    async def _download(self, image_url: str, *, allowed: frozenset[str]) -> bytes | None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, follow_redirects=False
            ) as client:
                response = await with_retry(
                    lambda: self._get(client, image_url, allowed=allowed), self._retry
                )
        except httpx.HTTPError:
            # Best-effort survives the retry: a failure that outlasts it is still no cover.
            return None
        if response is None:
            return None
        if not response.headers.get("content-type", "").startswith("image/"):
            return None
        content = response.content
        return content if len(content) <= self._max_bytes else None

    async def _get(
        self, client: httpx.AsyncClient, url: str, *, allowed: frozenset[str]
    ) -> httpx.Response | None:
        """GET ``url``, checking the address before each hop — ``None`` if any is refused."""
        for _ in range(_MAX_REDIRECTS + 1):
            if not await _may_fetch(url, allowed=allowed):
                return None
            response = await client.get(url)
            if response.next_request is None:
                response.raise_for_status()
                return response
            url = str(response.next_request.url)
        return None


async def _may_fetch(url: str, *, allowed: frozenset[str]) -> bool:
    """Whether every address ``url`` resolves to is public or already consented to."""
    addresses = await anyio.to_thread.run_sync(_resolve, url)
    return bool(addresses) and all(
        address in allowed or ipaddress.ip_address(address).is_global for address in addresses
    )


def _resolve(url: str) -> frozenset[str]:
    """Every address ``url``'s host resolves to; empty if it has none, or is not http(s).

    Resolving here and connecting later leaves a rebinding window: closing it would take
    a transport that pins the address it checked, which this adapter does not warrant.
    """
    parsed = urlparse(url)
    try:
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return frozenset()
        infos = socket.getaddrinfo(parsed.hostname, parsed.port, type=socket.SOCK_STREAM)
    except (socket.gaierror, ValueError):
        return frozenset()
    return frozenset(info[4][0] for info in infos)


def _year_from_date(value: str | None) -> int | None:
    """trafilatura normalises dates to ``YYYY-MM-DD`` — pull the leading year, if any."""
    if not value:
        return None
    match = re.search(r"\d{4}", value)
    return int(match.group()) if match else None
