# ADR-034: A Storage Call Budget and a Content-Read Deadline

**Status:** Accepted

> Refines the adapter of [ADR-007](007-s3-object-storage-adapter.md) and the content
> view of [ADR-019](019-admin-content-viewers-and-storage-backed-reads.md). The same
> move as [ADR-033](033-database-deadlines-and-pool-budget.md), one client over.

---

## Context

`boto3.client("s3", ...)` was constructed with no `Config`, so every storage call
carried botocore's unstated defaults: 60s to connect, 60s per socket read, five
attempts with backoff. A single stalled GET is therefore ~315s.

`get_document_content` issues one GET per chapter, sequentially, with no ceiling on the
loop. Multiply the two: a 40-chapter book against a backend that accepts connections and
then stalls is **≈3.5 hours inside one HTTP request**, holding an anyio thread token the
whole way. Neither number appears anywhere in the code.

---

## Decision

**One storage call has a stated budget.** `StoragePolicy` — a frozen value with a
default, following ADR-029's `RetryPolicy` and ADR-033's `EnginePolicy` — sets
`connect_timeout`, `read_timeout`, and `max_attempts` on a `botocore.config.Config`.
Attempts go through botocore's `total_max_attempts`, which counts tries; its
`max_attempts` key counts *retries*, and a budget off by one from its own name is not
a budget.

**The chapter loop has a total deadline.** `get_document_content` wraps its loop in
`anyio.fail_after`, so the read fails as a whole rather than accumulating per-object
worst cases. The deadline is a parameter with a default, so a caller can tighten it and
a test can pin it.

**Two bounds, because neither alone closes the hole.** A per-call budget still
multiplies by the chapter count; a loop deadline cannot interrupt a call already in
flight. Together the worst case is ~2 minutes.

---

## Consequences

- `anyio.to_thread.run_sync` defaults to `abandon_on_cancel=False`, so the deadline
  fires but does not return until the in-flight boto3 call does. The real ceiling is the
  deadline *plus* one call's budget: bounded, which is the point, but not exact.
- Expiry raises a bare `TimeoutError`, unmapped, so it surfaces as 500 (ADR-008). A
  stalling storage backend is the server's fault, and minting a domain error for an
  infrastructure condition would push transport concerns inward.
- The single-blob reads (`/file`, `/cover`) take the call budget and no deadline: one
  call is already bounded, and it was the loop that needed a second bound.
- These timeouts are a deployment guess, and a slow link plus a large source PDF is
  where a wrong guess shows first. They are visible and injectable, so moving one is an
  edit rather than an archaeology exercise.
- The loop stays sequential. A bare `gather` here would claim one thread token per
  chapter and starve dependency resolution — this ADR is about deadlines, not
  concurrency.
