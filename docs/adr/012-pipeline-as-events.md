# ADR-012: The Pipeline as Events

**Status:** Accepted

---

## Context

ADR-011 introduced the bus and refactored `UploadDocument` through it, but the
chain it exists for was still hand-wired: nothing yet *reacted* to an upload. The
first link of the pipeline — upload *causes* extraction — needs a producer (upload)
that names no consumer (extraction), so the two can be wired and rewired at the
composition root rather than calling each other directly.

---

## Decision

**The status machine finishes the event source (ADR-011).** `mark_ready()` raises
`ExtractionCompleted`, `mark_failed()` raises `ExtractionFailed` — the facts
summarization will subscribe to. No new concept: events ride the transitions that
already exist (ADR-002).

**Commands enter at the edge; internal reactions are events.** New messages reach
the bus queue only as events the aggregates raise (the UoW collects them) — a
handler never synthesises a command. So extraction is an **event handler on
`DocumentUploaded`** (`ExtractDocument`), not a command: upload *causes* extraction
with no producer→consumer coupling, and the bus keeps the collect-events-only shape
it had with one entry point. Commands are issued only by entrypoints — today the
HTTP routes (`UploadDocument`, `ListDocuments`, `DeleteDocument`).

**The remaining use cases become command handlers.** `ListDocuments` and
`DeleteDocument` take `(command, uow)` like `UploadDocument`; the bus supplies the
UoW, deps are injected at bootstrap. Routes issue commands and the per-use-case
`Depends` providers retire. Reads ride the bus too — the CQRS exit (explicit
queries) noted in ADR-011 stays deferred.

---

## Consequences

- For now extraction runs **inline**, on the request path within the upload's
  `handle()` (no async transport yet). The echoed upload result still reflects
  creation (`UPLOADED`): extraction drives a *freshly loaded* aggregate, so the
  detached result a route serializes is untouched. The in-memory repository fake
  snapshots on commit to mirror that detachment.
- Moving extraction off the request path means adding a new **entrypoint** — an
  in-process job queue — that issues an extraction *command* at the edge (where
  commands belong). The `DocumentUploaded` handler then enqueues a job instead of
  extracting inline; producers are untouched.
- An event with several aggregate-touching handlers over one shared UoW is not yet
  exercised; the bus drains `seen` after each message, which suffices while each
  reaction owns its transaction. Revisit when a second handler (summarization) joins
  `ExtractionCompleted`.
