"""`TrafilaturaArticleCoverRenderer` adapter logic (ADR-028).

trafilatura's fetch/metadata calls are stubbed and the image GET runs over a mocked
httpx transport, so these isolate the adapter's own decisions — the og:image
lookup, the scheme/content-type/size guards, and the best-effort None on failure —
with no network.
"""

import socket
from types import SimpleNamespace

import httpx
import pytest
import trafilatura

from cicero.adapters.enrichment.cover.trafilatura import TrafilaturaArticleCoverRenderer
from cicero.adapters.http.retry import RetryPolicy
from tests.fakes.http import replaying_transport, status

_JPEG = b"\xff\xd8\xff\xe0JPEGDATA"

# The hostnames these tests use, and what they resolve to. `internal.test` is the
# interesting one: a name whose address is private, which no check on the URL string
# can catch.
_HOSTS = {
    "cdn.test": "93.184.216.34",
    "other-cdn.test": "93.184.216.35",
    "internal.test": "10.0.0.5",
}


@pytest.fixture(autouse=True)
def _resolver(monkeypatch):
    """Resolve the test hostnames in-process — a unit test must not touch DNS."""

    def getaddrinfo(host, port, *args, **kwargs):
        try:
            socket.inet_aton(host)
        except OSError:
            if host not in _HOSTS:
                raise socket.gaierror(f"unstubbed host: {host}") from None
            host = _HOSTS[host]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


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


def _redirecting_transport(*, to: str) -> httpx.MockTransport:
    """Every URL but ``to`` answers with a 302 to it; ``to`` serves the image."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == to:
            return httpx.Response(200, content=_JPEG, headers={"content-type": "image/jpeg"})
        return httpx.Response(302, headers={"location": to})

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

    async def test_an_image_url_on_a_link_local_address_returns_no_cover(self, monkeypatch):
        # http:// passes any scheme check, so the scheme is not the guard that matters:
        # this is the cloud metadata endpoint, and its body would be stored as a cover.
        _stub_page(monkeypatch, image="http://169.254.169.254/latest/meta-data/")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert (await renderer.fetch_cover("https://example.com/a")).image is None

    async def test_an_image_host_resolving_to_a_private_address_returns_no_cover(
        self, monkeypatch
    ):
        # Nothing about this URL's text is suspicious — only its address is. The guard
        # has to resolve the host, not inspect the string.
        _stub_page(monkeypatch, image="https://internal.test/cover.jpg")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert (await renderer.fetch_cover("https://example.com/a")).image is None

    async def test_a_redirect_into_a_private_address_returns_no_cover(self, monkeypatch):
        # The og:image is on an ordinary public CDN; the 302 is where it goes private.
        # A check applied once, before the first request, never sees this hop.
        _stub_page(monkeypatch, image="https://cdn.test/cover.jpg")
        renderer = TrafilaturaArticleCoverRenderer(
            transport=_redirecting_transport(to="http://169.254.169.254/latest/meta-data/")
        )

        assert (await renderer.fetch_cover("https://example.com/a")).image is None

    async def test_an_internal_page_may_still_illustrate_itself(self, monkeypatch):
        # Same private host as the test above, but here the operator typed that address
        # themselves — the page's own image adds no reach they had not already granted.
        _stub_page(monkeypatch, image="http://internal.test/logo.png")
        renderer = TrafilaturaArticleCoverRenderer(transport=_image_transport())

        assert (await renderer.fetch_cover("http://internal.test/page")).image == _JPEG

    async def test_a_transient_failure_on_the_image_is_retried(self, monkeypatch):
        _stub_page(monkeypatch, image="https://cdn.test/cover.jpg")
        requests: list[httpx.Request] = []
        renderer = TrafilaturaArticleCoverRenderer(
            retry=RetryPolicy(backoff=0.0),
            transport=replaying_transport(
                [
                    status(503),
                    lambda: httpx.Response(
                        200, content=_JPEG, headers={"content-type": "image/jpeg"}
                    ),
                ],
                requests,
            ),
        )

        assert (await renderer.fetch_cover("https://example.com/a")).image == _JPEG
        assert len(requests) == 2

    async def test_exhausted_retries_still_leave_the_cover_best_effort(self, monkeypatch):
        # Bounded, and still no raise: enrichment completes with no cover (ADR-028/029).
        _stub_page(monkeypatch, image="https://cdn.test/cover.jpg")
        requests: list[httpx.Request] = []
        renderer = TrafilaturaArticleCoverRenderer(
            retry=RetryPolicy(backoff=0.0),
            transport=replaying_transport([status(503)], requests),
        )

        assert (await renderer.fetch_cover("https://example.com/a")).image is None
        assert len(requests) == 3

    async def test_a_redirect_between_public_hosts_still_returns_the_cover(self, monkeypatch):
        # The counterweight: CDNs redirect constantly, so the fix must re-check each hop
        # rather than simply refusing to follow them.
        _stub_page(monkeypatch, image="https://cdn.test/cover.jpg")
        renderer = TrafilaturaArticleCoverRenderer(
            transport=_redirecting_transport(to="https://other-cdn.test/cover.jpg")
        )

        assert (await renderer.fetch_cover("https://example.com/a")).image == _JPEG
