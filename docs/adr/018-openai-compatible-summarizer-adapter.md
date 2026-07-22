# ADR-018: Real Summarizer Adapter — OpenAI-Compatible, Config-Selected

**Status:** Accepted

> Delivers the "later increment" [ADR-016](016-ai-summaries-and-the-summary-read-model.md)
> foresaw: the first real adapter behind the `DocumentSummarizer` port, keeping
> `MockSummarizer` as the default.

---

## Context

`SummariseDocument` drives the read experience through the `DocumentSummarizer`
port; only `MockSummarizer` (canned text) implements it. A real summary needs an
LLM — but turnkey `docker compose up` must keep working with no key and no
external service. So a real adapter has to be *opt-in*, not the default.

---

## Decision

**`OpenAISummarizer`** (`adapters/summarization/openai.py`) calls any
OpenAI-compatible `/chat/completions` endpoint over `httpx`: a system + user
message (the extracted Markdown), returning `choices[0].message.content`. A
`Bearer` header is sent only when an API key is configured, so key-less local
endpoints (Ollama, vLLM) work unchanged. One `AsyncClient` per call — summaries
are infrequent (one per document); a 60s timeout; `raise_for_status()` so a bad
response surfaces as the existing `FAILED` terminal (the stage already swallows
summarizer errors).

**Config-selected in the composition root** — `LLM_BASE_URL` set →
`OpenAISummarizer`; unset → `MockSummarizer` stays the zero-config default. New
`LLM_*` settings (`base_url`, `api_key`, `model`) flow through `.env.example` and
compose, empty by default.

**Tested against a stubbed `httpx` transport** — asserts the request shape and
the response parse, no network. Integration and e2e keep the mock: **no live LLM
in CI.**

---

## Consequences

- Establishes the OpenAI-compatible request/parse pattern the later external-AI
  stages (podcast script, chat, enrichment) reuse behind their own ports — same
  shape, different prompt.
- `httpx` becomes a direct dependency (was transitive via `fastapi[standard]`);
  this adapter is its only runtime user.
- `LLM_BASE_URL` includes the version segment (e.g. `.../v1`), matching the
  OpenAI-client convention; the adapter appends `/chat/completions` and is
  agnostic to a trailing slash.
- No import-linter change: adapter in `adapters`, port in `domain`.
