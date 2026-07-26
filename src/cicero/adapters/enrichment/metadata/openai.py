from __future__ import annotations

import json

import httpx

from cicero.domain.document.ports.metadata_inferer import InferredMetadata, MetadataInferer

_SYSTEM_PROMPT = (
    "From the opening of a document, identify its author(s) and publication year. "
    'Reply with only a JSON object {"authors": string|null, "year": integer|null}; '
    "use null for anything the text does not state. Join multiple authors with commas."
)


class OpenAIMetadataInferer(MetadataInferer):
    """`MetadataInferer` over any OpenAI-compatible ``/chat/completions`` endpoint
    (ADR-028), mirroring the summarizer (ADR-018). Config-selected; the mock stays
    the zero-config default.

    Metadata lives in the opening, so only the first ``max_input_chars`` are sent —
    no map-reduce. The reply is parsed as JSON; a malformed reply yields empty
    metadata rather than raising, keeping enrichment best-effort.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        max_input_chars: int = 8_000,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._max_input_chars = max_input_chars
        self._timeout = httpx.Timeout(timeout)
        self._transport = transport

    async def infer(self, text: str) -> InferredMetadata:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text[: self._max_input_chars]},
            ],
        }
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self._url, json=payload, headers=headers)
            response.raise_for_status()
        return _parse(response.json()["choices"][0]["message"]["content"])


def _parse(content: str) -> InferredMetadata:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return InferredMetadata()
    if not isinstance(data, dict):
        return InferredMetadata()
    authors = data.get("authors")
    return InferredMetadata(
        authors=authors if isinstance(authors, str) and authors.strip() else None,
        year=_coerce_year(data.get("year")),
    )


def _coerce_year(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None
