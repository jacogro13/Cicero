"""`TrafilaturaArticleCoverRenderer` adapter logic (ADR-028).

trafilatura's fetch/metadata calls are stubbed and the image GET runs over a mocked
httpx transport, so these isolate the adapter's own decisions — the og:image
lookup, the scheme/content-type/size guards, and the best-effort None on failure —
with no network.
"""

from types import SimpleNamespace

import httpx
import trafilatura

from cicero.adapters.enrichment.cover.trafilatura import TrafilaturaArticleCoverRenderer

_JPEG = b"\xff\xd8\xff\xe0JPEGDATA"


def _stub_page(monkeypatch, *, html="<html></html>", image="https://cdn.test/cover.jpg"):
    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: html)
    metadata = None if image is None else SimpleNamespace(image=image)
    monkeypatch.setattr(trafilatura, "extract_metadata", lambda html: metadata)


def _image_transport(
    *, status=200, content=_JPEG, content_type="image/jpeg"
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


class TestTrafilaturaArticleCoverRenderer:
    async def test_fetches_the_og_image_bytes(self, monkeypatch):
        _stub_page(monkeypatch, image="https://cdn.test/cover.jpg")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        cover = await renderer.fetch_cover("https://example.com/a")

        assert cover == _JPEG

    async def test_no_og_image_returns_none(self, monkeypatch):
        _stub_page(monkeypatch, image=None)
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert await renderer.fetch_cover("https://example.com/a") is None

    async def test_a_failed_page_fetch_returns_none(self, monkeypatch):
        _stub_page(monkeypatch, html=None)
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert await renderer.fetch_cover("https://example.com/a") is None

    async def test_a_non_image_response_returns_none(self, monkeypatch):
        _stub_page(monkeypatch)
        renderer = TrafilaturaArticleCoverRenderer(
            transport=_image_transport(content_type="text/html")
        )

        assert await renderer.fetch_cover("https://example.com/a") is None

    async def test_an_oversized_image_returns_none(self, monkeypatch):
        _stub_page(monkeypatch)
        renderer = TrafilaturaArticleCoverRenderer(
            max_bytes=4, transport=_image_transport(content=b"x" * 100)
        )

        assert await renderer.fetch_cover("https://example.com/a") is None

    async def test_a_non_http_image_url_returns_none(self, monkeypatch):
        # A data: URI never reaches the network — the scheme guard drops it (SSRF-ish).
        _stub_page(monkeypatch, image="data:image/png;base64,AAAA")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert await renderer.fetch_cover("https://example.com/a") is None
