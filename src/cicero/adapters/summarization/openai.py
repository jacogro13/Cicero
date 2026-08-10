from __future__ import annotations

import httpx

from cicero.adapters.http.retry import DEFAULT_RETRY, RetryPolicy, post_json
from cicero.domain.document.content_chunking import split_for_budget
from cicero.domain.document.ports.document_summarizer import DocumentSummarizer

_SYSTEM_PROMPT = "Summarise the following document concisely and faithfully."
_CHUNK_PROMPT = (
    "Summarise the following excerpt from a longer document concisely and "
    "faithfully. It is one consecutive slice, not the whole document."
)
_SYNTHESIS_PROMPT = (
    "The following are summaries of consecutive sections of one document, in "
    "order. Synthesise them into a single concise, faithful summary of the whole."
)


class OpenAISummarizer(DocumentSummarizer):
    """`DocumentSummarizer` over any OpenAI-compatible ``/chat/completions`` endpoint
    (ADR-018). Config-selected; ``MockSummarizer`` stays the zero-config default.

    ``base_url`` includes the version segment (e.g. ``.../v1``); a ``Bearer`` header
    is sent only when an API key is set, so key-less local endpoints work unchanged.

    Input longer than ``max_input_chars`` is summarised by **map-reduce** (ADR-020):
    ``split_for_budget`` slices it, each slice is summarised, and the parts are
    synthesised into one summary. Input that fits is a single call.

    Every call is retried within ``retry`` while it fails transiently (ADR-029).
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        max_input_chars: int = 100_000,
        timeout: float = 60.0,
        retry: RetryPolicy = DEFAULT_RETRY,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._max_input_chars = max_input_chars
        self._timeout = httpx.Timeout(timeout)
        self._retry = retry
        self._transport = transport

    async def summarize(self, markdown: str) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            if len(markdown) <= self._max_input_chars:
                return await self._complete(client, headers, _SYSTEM_PROMPT, markdown)

            parts = [
                await self._complete(client, headers, _CHUNK_PROMPT, chunk)
                for chunk in split_for_budget(markdown, self._max_input_chars)
            ]
            return await self._complete(client, headers, _SYNTHESIS_PROMPT, "\n\n".join(parts))

    async def _complete(
        self, client: httpx.AsyncClient, headers: dict[str, str], system: str, content: str
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }
        response = await post_json(
            client, self._url, json=payload, headers=headers, policy=self._retry
        )
        return response.json()["choices"][0]["message"]["content"]
