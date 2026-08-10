"""`OpenAISummarizer` against a stubbed httpx transport (ADR-018): assert the
Chat Completions request shape, that the reply's content is returned, and that a
flaky upstream is retried within bounds (ADR-029). No network, no live LLM.
"""

from __future__ import annotations

import json

import httpx
import pytest

from cicero.adapters.http.retry import RetryPolicy
from cicero.adapters.summarization.openai import OpenAISummarizer
from tests.fakes.http import replaying_transport, status

_COMPLETION = {"choices": [{"message": {"role": "assistant", "content": "A real summary."}}]}


def _transport(capture: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        capture["request"] = request
        return httpx.Response(200, json=_COMPLETION)

    return httpx.MockTransport(handler)


async def test_posts_markdown_and_returns_the_completion_content():
    capture: dict = {}
    summarizer = OpenAISummarizer(
        base_url="https://llm.test/v1",
        model="some-model",
        api_key="sk-test",
        transport=_transport(capture),
    )

    summary = await summarizer.summarize("# Title\n\nBody.")

    assert summary == "A real summary."
    request = capture["request"]
    assert request.method == "POST"
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer sk-test"
    body = json.loads(request.content)
    assert body["model"] == "some-model"
    assert body["messages"][-1]["content"] == "# Title\n\nBody."


async def test_omits_authorization_without_an_api_key():
    capture: dict = {}
    summarizer = OpenAISummarizer(
        base_url="https://llm.test/v1", model="m", transport=_transport(capture)
    )

    await summarizer.summarize("text")

    assert "authorization" not in capture["request"].headers


def _counting_transport(requests: list[httpx.Request]) -> httpx.MockTransport:
    """Records every request and returns a distinct ``part N`` per call, so the
    synthesis (reduce) call can be checked to receive the mapped part summaries.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        content = f"part {len(requests)}"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


async def test_short_input_is_a_single_call():
    requests: list[httpx.Request] = []
    summarizer = OpenAISummarizer(
        base_url="https://llm.test/v1",
        model="m",
        max_input_chars=1000,
        transport=_counting_transport(requests),
    )

    summary = await summarizer.summarize("short body")

    assert len(requests) == 1
    assert summary == "part 1"


async def test_oversized_input_maps_each_chunk_then_reduces():
    requests: list[httpx.Request] = []
    summarizer = OpenAISummarizer(
        base_url="https://llm.test/v1",
        model="m",
        max_input_chars=10,
        transport=_counting_transport(requests),
    )

    # Three 4-char paragraphs pack into two 10-char chunks → 2 maps + 1 reduce.
    summary = await summarizer.summarize("aaaa\n\nbbbb\n\ncccc")

    assert len(requests) == 3
    reduce_request = json.loads(requests[-1].content)
    reduce_input = reduce_request["messages"][-1]["content"]
    assert "part 1" in reduce_input and "part 2" in reduce_input
    assert summary == "part 3"


# Backoff zeroed so the suite never sleeps; the delay itself is pinned in
# `test_outbound_retry.py`.
_NO_WAIT = RetryPolicy(backoff=0.0)


def _completion() -> httpx.Response:
    return httpx.Response(200, json=_COMPLETION)


def _summarizer(outcomes, requests) -> OpenAISummarizer:
    return OpenAISummarizer(
        base_url="https://llm.test/v1",
        model="m",
        retry=_NO_WAIT,
        transport=replaying_transport(outcomes, requests),
    )


class TestRetry:
    async def test_a_transient_failure_is_retried_and_the_summary_still_returns(self):
        requests: list[httpx.Request] = []
        summarizer = _summarizer([status(502), status(503), _completion], requests)

        assert await summarizer.summarize("body") == "A real summary."
        assert len(requests) == 3

    async def test_a_connection_timeout_is_retried(self):
        requests: list[httpx.Request] = []

        def timeout() -> httpx.Response:
            raise httpx.ConnectTimeout("upstream did not answer")

        summarizer = _summarizer([timeout, _completion], requests)

        assert await summarizer.summarize("body") == "A real summary."
        assert len(requests) == 2

    async def test_the_attempts_are_bounded(self):
        # An upstream that is down stays down: the call must fail rather than loop, so
        # the handler can commit FAILED (ADR-014).
        requests: list[httpx.Request] = []
        summarizer = _summarizer([status(500)], requests)

        with pytest.raises(httpx.HTTPStatusError):
            await summarizer.summarize("body")
        assert len(requests) == 3

    async def test_a_client_error_is_not_retried(self):
        # 400 means the request itself is wrong — repeating it only spends the budget.
        requests: list[httpx.Request] = []
        summarizer = _summarizer([status(400)], requests)

        with pytest.raises(httpx.HTTPStatusError):
            await summarizer.summarize("body")
        assert len(requests) == 1
