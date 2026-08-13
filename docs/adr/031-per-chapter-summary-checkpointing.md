# ADR-031: Per-Chapter Summary Checkpointing

**Status:** Accepted

> Relaxes the same-transaction projection of
> [ADR-016](016-ai-summaries-and-the-summary-read-model.md) and makes good on the
> promise of [ADR-030](030-retrying-a-failed-document.md).

---

## Context

Chapter summaries accumulated in a list and committed once, after the last one. A
failure — or a crash — at chapter 39 of 40 therefore threw away 39 LLM calls that had
already been paid for and left the document at `SUMMARISING`, and the re-drive started
again at chapter 0 and bought all 40 a second time.

ADR-030 justified keeping the projections on a retry precisely so a re-run could skip
work already paid for. Only the extraction projections actually did: the summaries had
nothing to skip, because none of them existed until the stage finished.

---

## Decision

**Each summary commits as it is produced.** One transaction per chapter, not one for
the run. `mark_summarised()` then commits alone, as the fact that the run finished.

**Positions already present are not summarised again.** The stage reads the existing
summaries once, up front, and skips those indices before reaching the LLM. No schema
change and no duplicate rows: the read model already upserts on `(document_id,
position)` (ADR-016), so this is the loop's shape changing, nothing else.

**The saving transaction is also the deletion checkpoint.** It re-reads the document
and drops the summary if it has gone, which is the ADR-023 guarantee — the call in
flight is paid in full, nothing after it is bought — served by the same round trip.

---

## Consequences

- `SUMMARISED` ⇔ the summary is readable no longer holds; a partial summary is readable
  while `SUMMARISING`, and after a `FAILED`. The chapter view already modelled this
  (`summary: str | None` per chapter, ADR-021) and the SPA gates on `SUMMARISED`, so
  the whole-document summary is the only reader that can now see a partial answer.
- A retry after a failed chapter costs one chapter, not a book. This is the first place
  where the money and the wall clock diverge from each other in the pipeline.
- A re-drive reuses the summary at a position whose chapter content changed underneath
  it. Extraction is deterministic over a fixed blob, so this needs the extractor itself
  to change; the fix then is to drop the summaries, not to re-read them.
- n+1 transactions where there was one, all of them small, each dwarfed by the LLM call
  that precedes it.
