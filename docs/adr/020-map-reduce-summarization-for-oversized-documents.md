# ADR-020: Map-Reduce Summarization for Oversized Documents

**Status:** Accepted

> Extends [ADR-018](018-openai-compatible-summarizer-adapter.md): the real
> summarizer now survives inputs larger than the model's context window.

---

## Context

`OpenAISummarizer` sends the whole extracted Markdown as one `/chat/completions`
user message. A large document overflows the model's context window — the call
fails or the model silently truncates, so the tail is never summarised.
`MockSummarizer` is unaffected. The real adapter must handle inputs beyond the
model's budget, and it must do so **without a tokenizer dependency**.

---

## Decision

A **char budget** `max_input_chars` bounds the content of a single call.

- **Input ≤ budget → one call**, exactly as before (the common case).
- **Input > budget → map-reduce**: `split_for_budget` slices the Markdown into
  budget-sized chunks, each is summarised (**map**), and the part summaries are
  synthesised into one final summary (**reduce**).

`split_for_budget` (`domain/document/content_chunking.py`) is a **pure**
function: greedy paragraph packing that keeps fenced code blocks atomic; a lone
paragraph over budget is hard-split on character count (the last resort). It
lives in the domain layer, framework-free, so a later stage can reuse the same
slicing.

**Char budget, no tokenizer** — a chars-per-token approximation keeps the
dependency surface small. Config `LLM_SUMMARIZE_MAX_INPUT_CHARS` (default
`100_000` ≈ a 32k-context model with headroom for prompt + output); shrink it if
the served model's context is smaller.

**Single-level reduce** — part summaries are far shorter than their inputs, so
their concatenation fits one synthesis call; no recursion.

**Still no live LLM in CI** — tested against a stubbed transport asserting the
map-then-reduce call pattern; `MockSummarizer` stays the zero-config default.

---

## Consequences

- The chunker is **shared infrastructure**: the future embedding/retrieval index
  will reuse `split_for_budget` for its chunks — its home in `domain/` is chosen
  for that reuse, not only for this stage.
- Map-reduce multiplies calls (N maps + 1 reduce) for a large document; summaries
  are infrequent, so the cost is acceptable. One `AsyncClient` spans the whole
  map-reduce.
- A synthesised summary is a summary-of-summaries — some fidelity loss versus a
  single-context pass, the unavoidable price of exceeding the window.
