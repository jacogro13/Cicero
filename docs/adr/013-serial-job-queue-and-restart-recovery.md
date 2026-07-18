# ADR-013: Serial Job Queue and Restart Recovery

**Status:** Accepted

---

## Context

ADR-012 left extraction running **inline**, on the request path within the upload's
`handle()`. That does not hold as the pipeline grows: extraction (PyMuPDF) takes
seconds and the summaries and podcast ahead take minutes, so an upload would block
its HTTP response for the whole job. And a batch upload would start every job at
once — unbounded in-process work (PyMuPDF now, local LLM/TTS later) that exhausts
memory. Slow reactions need to run **off the request path, with a bound on how many
run at once**, while keeping the commands-at-the-edge rule of ADR-011/012.

---

## Decision

**An in-process serial `JobQueue` (`entrypoints/`) is the async transport.** It runs
jobs with a fixed number of workers (`concurrency`, default 1 → strictly one at a
time), so a batch upload can enqueue freely without ever running more than N heavy
jobs. It is created **per event loop in the lifespan** and held on `app.state` —
never a module global — so its `asyncio.Queue` cannot leak across loops.

**The queue carries document-id intents, not commands.** The `DocumentUploaded`
handler becomes `EnqueueExtraction`: it enqueues `event.document_id` and builds
nothing. The queue stays domain-agnostic — an intent is just "process this
document."

**The worker issues the command at the edge.** Each intent is dispatched through a
consumer wired at the composition root — `bus.handle(commands.ExtractDocument(id))`.
So `ExtractDocument` returns to being a **command** handler `(command, uow)`, and the
queue worker is the new edge that issues it: a handler still never synthesises a
command (ADR-012).

**The bus is built once, in the lifespan** (`app.state.bus`), so the worker and the
routes share it. `get_message_bus` returns it; the test seam moves up to the bus
(tests `bootstrap` with fakes), retiring the leaf-provider overrides.

**Restart recovery reconstructs work from persisted status, with no jobs table.** An
in-process queue loses whatever was mid-flight on a restart. On startup
`reconcile_processing_documents` re-enqueues every document left in `PROCESSING`;
`mark_processing()` is unguarded, so re-running extraction on a stuck document is
safe.

---

## Consequences

- Upload returns immediately with `UPLOADED`; the document reaches `READY`/`FAILED`
  asynchronously. Clients poll `GET` for the outcome (a push channel is deferred).
- Bounded concurrency is the memory guard for batch uploads; default 1 processes
  documents strictly in order.
- Recovery re-runs only from `PROCESSING`. A crash between the upload commit and the
  enqueue leaves an `UPLOADED` document unqueued — rare; revisit if it bites.
- The transport is generic: summaries and the podcast enqueue the same way, each a
  command the worker issues at the edge, so the pipeline extends without new wiring.
