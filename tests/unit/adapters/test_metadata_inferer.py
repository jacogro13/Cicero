"""The MetadataInferer adapters (ADR-028).

`MockMetadataInferer` is the zero-config default that infers nothing.
`OpenAIMetadataInferer` runs against a stubbed httpx transport: assert the request
shape, the JSON parse, and the best-effort fallbacks — no network, no live LLM.
"""

from __future__ import annotations

import json

import httpx

from cicero.adapters.enrichment.metadata.mock import MockMetadataInferer
from cicero.adapters.enrichment.metadata.openai import OpenAIMetadataInferer
from cicero.adapters.http.retry import RetryPolicy
from cicero.domain.document.ports.metadata_inferer import InferredMetadata
from tests.fakes.http import replaying_transport


async def test_mock_infers_nothing():
    assert await MockMetadataInferer().infer("some opening text") == InferredMetadata()


def _transport(reply: str, capture: dict | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["request"] = request
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    return httpx.MockTransport(handler)


class TestOpenAIMetadataInferer:
    async def test_posts_opening_text_and_parses_authors_and_year(self):
        capture: dict = {}
        inferer = OpenAIMetadataInferer(
            base_url="https://llm.test/v1",
            model="some-model",
            api_key="sk-test",
            transport=_transport(json.dumps({"authors": "Jane Doe", "year": 2003}), capture),
        )

        metadata = await inferer.infer("# Title\n\nby Jane Doe, 2003")

        assert metadata == InferredMetadata(authors="Jane Doe", year=2003)
        request = capture["request"]
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer sk-test"
        body = json.loads(request.content)
        assert body["model"] == "some-model"
        assert body["messages"][-1]["content"] == "# Title\n\nby Jane Doe, 2003"

    async def test_null_fields_become_none(self):
        inferer = OpenAIMetadataInferer(
            base_url="https://llm.test/v1",
            model="m",
            transport=_transport(json.dumps({"authors": None, "year": None})),
        )

        assert await inferer.infer("text") == InferredMetadata()

    async def test_an_unparseable_reply_yields_empty_metadata(self):
        inferer = OpenAIMetadataInferer(
            base_url="https://llm.test/v1", model="m", transport=_transport("not json at all")
        )

        assert await inferer.infer("text") == InferredMetadata()

    async def test_a_rate_limited_call_is_retried(self):
        # 429 is the one 4xx worth repeating: the server said later, not never (ADR-029).
        requests: list[httpx.Request] = []
        inferer = OpenAIMetadataInferer(
            base_url="https://llm.test/v1",
            model="m",
            retry=RetryPolicy(backoff=0.0),
            transport=replaying_transport(
                [
                    lambda: httpx.Response(429, headers={"retry-after": "0"}),
                    lambda: httpx.Response(
                        200,
                        json={
                            "choices": [
                                {"message": {"content": json.dumps({"authors": "Jane Doe"})}}
                            ]
                        },
                    ),
                ],
                requests,
            ),
        )

        assert await inferer.infer("text") == InferredMetadata(authors="Jane Doe")
        assert len(requests) == 2

    async def test_only_the_opening_slice_is_sent(self):
        capture: dict = {}
        inferer = OpenAIMetadataInferer(
            base_url="https://llm.test/v1",
            model="m",
            max_input_chars=10,
            transport=_transport(json.dumps({"authors": None, "year": None}), capture),
        )

        await inferer.infer("x" * 100)

        body = json.loads(capture["request"].content)
        assert len(body["messages"][-1]["content"]) == 10
