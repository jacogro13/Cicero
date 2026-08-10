"""A scripted upstream for the outbound httpx adapters (ADR-029) — one outcome per
request, so a flaky server is expressed as a list rather than a stateful stub.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx

Outcome = Callable[[], httpx.Response]


def replaying_transport(
    outcomes: Sequence[Outcome], requests: list[httpx.Request]
) -> httpx.MockTransport:
    """Play ``outcomes`` in order, repeating the last once they run out, recording every
    request. An outcome may raise instead of answering — that is the transport failing."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return outcomes[min(len(requests) - 1, len(outcomes) - 1)]()

    return httpx.MockTransport(handler)


def status(code: int) -> Outcome:
    """An outcome answering ``code`` with a body no adapter will read."""
    return lambda: httpx.Response(code, json={"error": "upstream"})
