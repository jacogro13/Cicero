# ADR-030: Retrying a Failed Document

**Status:** Accepted

> Settles the transition [ADR-002](002-document-status-state-machine.md) deferred, and
> leaves the stage table of [ADR-014](014-status-driven-pipeline-advance.md) untouched.

---

## Context

`FAILED` has no next command, so nothing re-drives it — not dispatch, not restart
recovery, since both ask the same `has_next_stage`. Bounded retry (ADR-029) absorbs a
transient blip, but a sustained outage, a bad API key, or a model that no longer exists
still lands a document there for good, and the only way out was to delete and re-upload
it: a new id, and the title or URL the operator typed retyped.

ADR-002 deferred this transition until the project needed it. It does now.

---

## Decision

**Explicit, never automatic.** A `RetryDocument` command — issued by a person through
`POST /documents/{id}/retry` — resets the document to `UPLOADED` and raises
`DocumentRetried`, which the existing `AdvanceDocument` subscriber enqueues. The stage
table is untouched: `FAILED` still maps to nothing, so restart recovery cannot re-drive
failures in a loop, and a permanently broken document stays quiet rather than spending
an LLM budget on every deploy.

**Back to the start, not to the failed stage.** `FAILED` does not record where it
happened, and inferring it from the projections would be a guess. Re-running from
extraction is safe because every write key is deterministic — same blob keys, same
chapter rows, same summary positions — so a re-drive overwrites and never duplicates.

**Guarded, unlike the `mark_*` methods.** Retrying anything but a `FAILED` document
raises `DocumentNotRetryable` → 409. ADR-002 left runtime guards to the method that
needed one; this is the first transition whose caller is a person rather than the
pipeline, so a wrong call is a client error and deserves a status code.

**The projections stay.** They are keyed by position and overwritten as the re-run
reaches them; keeping them is what lets a re-drive skip work already paid for instead
of buying every chapter summary a second time.

---

## Consequences

- A document that failed at summarisation re-pays extraction. Accepted over recording
  the failed stage on the aggregate — a column and a rule, for a case that is rare and
  cheap to overpay.
- `Document` now raises on a lifecycle call for the first time, so the aggregate holds
  both guarded and unguarded transitions. The split is by caller, not by taste: the
  pipeline's own `mark_*` calls stay unguarded.
- Retry is unbounded by design — an operator may re-drive the same document forever.
  Nothing automatic ever does, which is what keeps that safe.
- A re-run yielding *fewer* chapters leaves the surplus summaries behind: invisible in
  the table of contents, which zips with the current titles, but still concatenated
  into the whole-document summary.
- The enrichment branch keeps its own terminal `FAILED` (ADR-028); a re-driven document
  re-enters it anyway, since completing extraction is what feeds that branch.
