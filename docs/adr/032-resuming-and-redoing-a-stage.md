# ADR-032: Resuming and Redoing a Stage

**Status:** Accepted

> Amends [ADR-030](030-retrying-a-failed-document.md)'s "back to the start", and spends
> the checkpoint [ADR-031](031-per-chapter-summary-checkpointing.md) built.

---

## Context

Retry re-drives a failed document from `UPLOADED`, so a document that failed at
summarisation re-extracts a PDF it already extracted identically — ADR-030 accepted that
as cheap, but it is minutes of a person waiting for nothing.

The opposite need has no answer at all. ADR-031 made the summarise stage skip positions
that already have a summary, which is what stops a retry re-buying 39 chapters — and, by
the same rule, what makes a *deliberate* re-summarise impossible. Change the model or the
prompt and there is no way to ask for new summaries but by deleting the document.

---

## Decision

**The status is the resume point, and a projection is the record that a stage finished.**
So: to skip a stage, keep its projection; to redo one, discard it. Two verbs, one rule.

**Retry resumes at the furthest completed stage.** `RetryDocument` reads the chapter
projection and the aggregate resumes at `EXTRACTED` when it survived, at `UPLOADED`
otherwise. ADR-030 was right that `FAILED` cannot say *where* it failed; this infers
something else — what *completed* — and that is not a guess: `chapters.save()` and
`mark_extracted()` commit in one transaction, after the blobs are written, so chapter
rows exist only if extraction finished with its blobs in place. That is exactly the
precondition the summarise stage needs.

**Redoing a stage discards its projection first.** `ResummariseDocument` — a person's
command, like retry — drops the summaries and sets `EXTRACTED` in the same transaction,
so no reader ever sees a `SUMMARISED` document with no summary. The re-run then finds
nothing to skip and buys every chapter, which is the whole point of asking.

**Both refusals are 409s** on the existing `DocumentNotRetryable`, now carrying the
status it wanted. The name still reads as "cannot be re-driven from here"; a second
exception for one more status would buy nothing.

---

## Consequences

- Retry no longer re-enters the enrichment branch, which fed off `ExtractionCompleted`.
  It only ever did so incidentally: enrichment failing leaves the document `SUMMARISED`,
  which retry refuses anyway (ADR-028). The branch needs its own verb, when it needs one.
- Re-summarising is the first command that deliberately destroys a projection. It is
  also the only one that spends money on purpose, so it stays explicit and unguessable.
- The rule already names a third verb — discard the chapters, resume at `UPLOADED` — but
  nothing needs a forced re-extraction yet, so it is not built (ADR-011).
- A retry after extraction failed *on a re-run* resumes from the older chapter rows. Safe
  only because extraction over a fixed blob is deterministic: same count, same keys.
