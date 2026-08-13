# ADR-016: AI Summaries — a Pipeline Stage and its Read Model

**Status:** Accepted

> Partly superseded by [ADR-031](031-per-chapter-summary-checkpointing.md): the
> projection now commits a chapter at a time rather than with `mark_summarised()`, so
> `SUMMARISED` ⇔ readable no longer holds. Everything else below stands.

> Builds on [ADR-014](014-status-driven-pipeline-advance.md) (status names the
> stage; `SUMMARISING`/`SUMMARISED` were reserved there) and
> [ADR-015](015-cqrs-read-side.md) (reads bypass the bus; denormalized read models
> land "only where a view genuinely needs it"). Extends [ADR-009](009-content-extraction-and-the-extract-document-use-case.md)'s
> stage shape. This is the read experience: what the user actually reads.

---

## Context

Extraction leaves a document at `EXTRACTED` with internal Markdown at
`content_key` that the reader never sees. A summary *is* the read experience.
Producing it is a second slow stage — the first real test of the ADR-014 claim
that a stage costs one status, one `NEXT_COMMAND` entry, one subscription. The
extracted text is currently flat Markdown — no chapter structure, no document kind
yet — so this is **one summary per document**.

---

## Decision

**A stage on the conveyor, no new machinery.** Add `SUMMARISING`/`SUMMARISED` to
the linear spine (`EXTRACTED → SUMMARISING → SUMMARISED | FAILED`); add
`EXTRACTED → SummariseDocument` (and `SUMMARISING → SummariseDocument`, a re-run)
to `NEXT_COMMAND`; subscribe the existing `AdvanceDocument` to
`ExtractionCompleted`. Extraction completing now *causes* summarization — the bus
payoff. `SUMMARISED` raises no event (nothing consumes it yet; non-speculative,
per ADR-011).

**`DocumentSummarizer` port** (`domain/document/ports/`) — `summarize(markdown)
-> str`. `SummariseDocument` mirrors `ExtractDocument`: commit `SUMMARISING`
first, summarize outside any transaction, then persist. Failure → `FAILED`,
swallowed (status is the outcome channel). Unknown id → `DocumentNotFound`.

**Mock summarizer is the default adapter** — `MockSummarizer`
(`adapters/summarization/`), selected when no LLM endpoint is configured, so
`docker compose up` summarizes with zero external services. Any OpenAI-compatible
endpoint plugs in behind the same port (a later increment, no architecture change).

**The summary is a denormalized read model** (ADR-015's "where a view genuinely
needs it"). A `summaries` table, keyed by `document_id`, decoupled from the
`Document` aggregate — reached via `uow.summaries` (a `SummaryReadModel` port),
read directly by `views.get_document_summary` returning a `SummaryView`. The
summarisation stage **writes it in the same transaction as `mark_summarised()`**,
so `SUMMARISED` ⇔ the summary is readable. A separate event-driven *projector*
buys nothing while the source is one external call and the shape is a scalar; it
arrives when per-chapter structure makes the read shape diverge.

**The single failure terminal gets a single failure fact** — `ExtractionFailed`
is renamed `DocumentProcessingFailed` (stage-agnostic, matching ADR-014's single
`FAILED`). `GET /api/documents/{id}/summary` serves the view (404 until summarized).

---

## Consequences

- A second stage cost exactly what ADR-014 predicted — no new handler class, no
  branch in the composition root; the read side gained a divergent view for real.
- Read/write models split for the first time in storage: the view reads
  `summaries`, never the aggregate, so it cannot drift onto write-model fields.
- Same-transaction projection trades the book's eventual-consistency projector for
  strong consistency, justified while the projection source is a command, not a
  replayable event stream; revisit if a summary ever fans out to several views.
- No import-linter change: port in `domain`, adapter in `adapters`, view in
  `services`, route in `entrypoints`.
- `FAILED` stays single now that a second stage can fail — refreshing ADR-014's
  justification, which was "speculative until a second stage can fail". It holds
  for a sharper reason: dispatch treats every spine failure identically (next
  command `None`), and an eventual per-stage *retry* wants the failed stage
  as **data** (a resume point + reason a status can't carry), not more terminals.
  Later best-effort branches (enrichment, podcast, indexing) carry their own failure
  state, since those failures do not stop the read experience.
