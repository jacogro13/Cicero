"""Bounded retry shared by every outbound httpx adapter (ADR-029).

Retries what a retry can fix — connection errors, timeouts, 429, 5xx — and nothing
else, a bounded number of times, with jittered backoff.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import anyio
import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try one outbound call: ``attempts`` in total, waiting ``backoff``
    seconds after the first failure and doubling from there, never past ``max_backoff``."""

    attempts: int = 3
    backoff: float = 0.5
    max_backoff: float = 10.0


DEFAULT_RETRY = RetryPolicy()


def retry_delay(attempt: int, policy: RetryPolicy, retry_after: float | None = None) -> float:
    """Seconds to wait before ``attempt`` (1-based): what the server asked for, else
    exponential backoff with full jitter — the spread is what keeps callers that failed
    together from returning together. Capped either way."""
    if retry_after is not None:
        return min(retry_after, policy.max_backoff)
    return random.uniform(0.0, min(policy.backoff * 2 ** (attempt - 1), policy.max_backoff))


async def with_retry[T](
    call: Callable[[], Awaitable[T]], policy: RetryPolicy = DEFAULT_RETRY
) -> T:
    """Await ``call``, retrying transient failures within ``policy``. The last failure
    is raised once the attempts are spent, so the caller still decides what it means."""
    attempt = 0
    while True:
        try:
            return await call()
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            attempt += 1
            if attempt >= policy.attempts or not _is_transient(error):
                raise
            delay = retry_delay(attempt, policy, _retry_after(error))
            logger.warning(
                "Retrying outbound call in %.2fs after %s (attempt %d/%d)",
                delay,
                type(error).__name__,
                attempt,
                policy.attempts,
            )
            await anyio.sleep(delay)


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    json: dict,
    headers: dict[str, str],
    policy: RetryPolicy = DEFAULT_RETRY,
) -> httpx.Response:
    """POST ``json`` and return the 2xx response, retrying per ``policy``."""

    async def send() -> httpx.Response:
        response = await client.post(url, json=json, headers=headers)
        response.raise_for_status()
        return response

    return await with_retry(send, policy)


def _is_transient(error: Exception) -> bool:
    """A connection failure or timeout always; a status only when the server said
    later (429) or broke (5xx) — any other 4xx is this request's own fault."""
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return True


def _retry_after(error: Exception) -> float | None:
    """The server's ``Retry-After``, delay-seconds form only; the HTTP-date form falls
    back to the computed backoff rather than growing a date parser."""
    if not isinstance(error, httpx.HTTPStatusError):
        return None
    try:
        return float(error.response.headers.get("retry-after", ""))
    except ValueError:
        return None
