# ADR-023: Deleting a Document Mid-Pipeline

**Status:** Accepted

> Extends the "stale intent is not an error" rule of
> [ADR-014](014-status-driven-pipeline-advance.md) from dispatch to the stage
> handlers, and the delete cleanup of [ADR-004](004-object-storage-port-and-services-layer.md)
> to the read-model projections.

---

## Context

The serial worker (ADR-013) runs a stage to completion before taking the next
intent. Deleting a document while it is `EXTRACTING`/`SUMMARISING` broke three ways:
the stage's commit-back re-read the document, got `None`, and crashed on `mark_*`;
the deletion removed only the metadata and source blob, orphaning the chapter-title
and summary projections plus the chapter blobs; and the worker kept spending a full
extraction — or LLM call — on a document already gone, starving every later upload.

The dispatch edge already treats a document deleted between enqueue and dispatch as a
dropped intent, not an error (ADR-014). The stage handlers did not extend that inward.

---

## Decision

**A document deleted mid-stage is dropped, not failed.** Each stage re-checks
existence at its commit-back; a missing document logs and returns, leaving nothing
half-written. Extraction also checks before writing any chapter blob, so a dropped
extraction leaves no orphans.

**Summarization re-checks between chapters.** `_summarise_chapters` reads existence
before each chapter's LLM call and stops early, bounding the work wasted on a deleted
document to at most the call already in flight. Cancelling that in-flight call is out
of scope — it needs cancellation plumbing the serial queue does not have, weighed
against saving one call. Left as a considered alternative.

**Delete tears down everything the document owns.** `DeleteDocument` drops the chapter
and summary projections in the same transaction as the metadata, then sweeps the
`documents/{id}/` storage prefix — source and every chapter blob, orphans included.

**The UI names the wait.** A serial queue means a document that has finished one stage
waits behind the current job for the next, so the pre-work states (`UPLOADED`,
`EXTRACTED`) read as "Queued"; the tooltip names which stage is pending, so the two
are still distinguishable and neither reads as a silent stall.

---

## Consequences

- The "deleted mid-flight is not an error" contract now holds end to end, from the
  edge through both stages; the commit-back can no longer crash on a concurrent delete.
- A deleted document leaves no orphan rows or blobs — cleanup is the delete's job, not
  a later sweep, matching the projections' explicit-teardown model (ADR-015/016).
- Wasted work on a deleted document is bounded per chapter, not per document; a single
  long call still completes. Full cancellation stays available if it ever bites.
- `delete_prefix` joins the storage port; a listing adapter (S3 `list_objects_v2`)
  now backs it.
