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


def _stub_page(
    monkeypatch,
    *,
    html="<html></html>",
    image="https://cdn.test/cover.jpg",
    author=None,
    date=None,
):
    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: html)
    metadata = (
        None
        if (image is None and author is None and date is None)
        else SimpleNamespace(image=image, author=author, date=date)
    )
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

        fetched = await renderer.fetch_cover("https://example.com/a")

        assert fetched.image == _JPEG

    async def test_surfaces_the_bylines_author_and_year(self, monkeypatch):
        # The structured metadata harvested alongside the cover — the URL branch's
        # primary source of authors/year (ADR-028 amendment).
        _stub_page(monkeypatch, author="Jane Roe", date="2021-05-04")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        fetched = await renderer.fetch_cover("https://example.com/a")

        assert fetched.author == "Jane Roe"
        assert fetched.year == 2021

    async def test_no_og_image_still_returns_the_byline(self, monkeypatch):
        # No cover, but the page still stated an author — the byline is not lost.
        _stub_page(monkeypatch, image=None, author="Jane Roe", date="2021-05-04")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        fetched = await renderer.fetch_cover("https://example.com/a")

        assert fetched.image is None
        assert fetched.author == "Jane Roe"

    async def test_no_og_image_returns_no_cover(self, monkeypatch):
        _stub_page(monkeypatch, image=None)
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert (await renderer.fetch_cover("https://example.com/a")).image is None

    async def test_a_failed_page_fetch_returns_nothing(self, monkeypatch):
        _stub_page(monkeypatch, html=None)
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        fetched = await renderer.fetch_cover("https://example.com/a")

        assert fetched.image is None
        assert fetched.author is None

    async def test_a_non_image_response_returns_no_cover(self, monkeypatch):
        _stub_page(monkeypatch)
        renderer = TrafilaturaArticleCoverRenderer(
            transport=_image_transport(content_type="text/html")
        )

        assert (await renderer.fetch_cover("https://example.com/a")).image is None

    async def test_an_oversized_image_returns_no_cover(self, monkeypatch):
        _stub_page(monkeypatch)
        renderer = TrafilaturaArticleCoverRenderer(
            max_bytes=4, transport=_image_transport(content=b"x" * 100)
        )

        assert (await renderer.fetch_cover("https://example.com/a")).image is None

    async def test_a_non_http_image_url_returns_no_cover(self, monkeypatch):
        # A data: URI never reaches the network — the scheme guard drops it (SSRF-ish).
        _stub_page(monkeypatch, image="data:image/png;base64,AAAA")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert (await renderer.fetch_cover("https://example.com/a")).image is None
