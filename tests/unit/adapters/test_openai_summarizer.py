"""`OpenAISummarizer` against a stubbed httpx transport (ADR-018): assert the
Chat Completions request shape and that the reply's content is returned. No
network, no live LLM.
"""

from __future__ import annotations

import json

import httpx

from cicero.adapters.summarization.openai import OpenAISummarizer

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
