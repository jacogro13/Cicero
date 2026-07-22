from __future__ import annotations

import httpx

from cicero.domain.document.ports.document_summarizer import DocumentSummarizer

_SYSTEM_PROMPT = "Summarise the following document concisely and faithfully."


class OpenAISummarizer(DocumentSummarizer):
    """`DocumentSummarizer` over any OpenAI-compatible ``/chat/completions`` endpoint
    (ADR-018). Config-selected; ``MockSummarizer`` stays the zero-config default.

    ``base_url`` includes the version segment (e.g. ``.../v1``); a ``Bearer`` header
    is sent only when an API key is set, so key-less local endpoints work unchanged.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout)
        self._transport = transport

    async def summarize(self, markdown: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": markdown},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
