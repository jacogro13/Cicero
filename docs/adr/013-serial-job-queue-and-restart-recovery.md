# ADR-013: Serial Job Queue and Restart Recovery

**Status:** Accepted

---

## Context

ADR-012 left extraction **inline**, on the request path within the upload's
`handle()`. That does not scale: extraction (PyMuPDF) takes seconds and the
summaries and podcast ahead take minutes, so upload would block its HTTP response
for the whole job — and a batch upload would start every job at once, unbounded
in-process work (local LLM/TTS later) that exhausts memory. Slow reactions must run
**off the request path, bounded**, while keeping commands-at-the-edge (ADR-011/012).

---

## Decision

**An in-process serial `JobQueue` (`entrypoints/`) is the async transport.** Workers
drain it at a fixed `concurrency` (default 1), so a batch upload can enqueue freely
without ever running more than N heavy jobs. Created **per event loop in the
lifespan** and held on `app.state` — never a module global, so no cross-loop leak.

**The queue carries document-id intents, not commands.** The `DocumentUploaded`
handler becomes `EnqueueExtraction`: it enqueues `event.document_id` and builds
nothing. The queue stays domain-agnostic — an intent is just "process this document."

*Rejected: enqueuing the command itself.* Simpler, and the transport would be generic
for free — one `bus.handle(command)` consumer serves every job type. But command
origination would disperse across handlers (today it is greppable in `entrypoints/`
alone), and a handler free to issue commands can issue several conditionally — a saga
inside an event subscriber. Discipline alone enforces this; `commands` imports cleanly.

**The worker issues the command at the edge.** Each intent is dispatched through a
consumer wired at the composition root — `bus.handle(commands.ExtractDocument(id))`.
So `ExtractDocument` is again a command handler `(command, uow)`, and the worker is
the new edge that issues it: a handler still never synthesises a command (ADR-012).

**The bus is built once, in the lifespan** (`app.state.bus`), shared by worker and
routes. The test seam moves up to it (tests `bootstrap` with fakes).

**Restart recovery reconstructs work from persisted status, with no jobs table.** An
in-process queue loses whatever was mid-flight. On startup `reconcile_processing_documents`
re-enqueues every document left in `PROCESSING`; `mark_processing()` is unguarded, so
re-running extraction on a stuck document is safe.

---

## Consequences

- Upload returns immediately with `UPLOADED`; the document reaches `READY`/`FAILED`
  asynchronously. Clients poll `GET` for the outcome (a push channel is deferred).
- Bounded concurrency is the memory guard for batch uploads; default 1 processes
  documents strictly in order.
- Recovery re-runs only from `PROCESSING`. A crash between the upload commit and the
  enqueue leaves an `UPLOADED` document unqueued — rare; revisit if it bites.
- A second job type forces the edge to learn which command an intent means — either a
  kind tag on the intent, or deriving it from the document's persisted status (which
  would also fold recovery into the normal path). Decided when the second job type
  lands (summaries).
