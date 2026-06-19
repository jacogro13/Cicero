# ADR-009: Content Extraction (PDF → Markdown) and the ExtractDocument Use Case

**Status:** Accepted

> Builds on [ADR-002](002-document-status-state-machine.md) (the status state
> machine + `content_key`), [ADR-004](004-object-storage-port-and-services-layer.md)
> (the `DocumentStorage` port + storage-first ordering), and
> [ADR-007](007-s3-object-storage-adapter.md) (anyio-offloaded blocking I/O). It
> turns an uploaded source into the internal text that summarization will read.

---

## Context

An uploaded document sits at `UPLOADED` with its source bytes in storage and no
extracted text. Summarization (and chat) need that text as Markdown; the reader
never sees it (the source is read from the original PDF). Producing it is a use
case, and it must reach a PDF library without the domain knowing which one
(ADR-001). It also drives the rest of the status machine for real.

---

## Decision

**`DocumentExtractor` port** (`domain/document/ports/`) — `extract_markdown(data)
-> str`. PDF bytes in, one Markdown string out. No filename, no URL, no chapter
structure yet: URL ingest and TOC-driven headings are later slices that extend the
port when they land.

**`ExtractDocument` use case** (`services/document/`) — `execute(document_id)`.
Commits `PROCESSING` first (so the in-flight state is observable), then does the
heavy I/O outside any transaction, then commits the outcome. Unknown id →
`DocumentNotFound`.

**Storage-first, mirroring upload (ADR-004):** write the extracted Markdown blob
to `document.content_key`, *then* commit `READY`. A `READY` document therefore
never points at a missing content file; the only failure residue is a harmless
orphan blob. `content_key` is `documents/{id}/content` — an **identity-derived
address owned by the domain** (`source_key`'s twin), so the service never mints a
storage key, and `mark_ready()` only flips status: readiness is `status` alone
(ADR-002), not a nullable field the service has to populate.

**Extraction failure marks `FAILED` and is swallowed** — status is the outcome
channel for what becomes a background job; a raised exception would have nowhere
to go. The id-not-found case is the exception — a programming error, surfaced.

**`get` joins the `DocumentStorage` port** (it was an in-memory test helper) —
extraction is the first reader of stored bytes; the S3 adapter implements it.

**`PyMuPDFExtractor`** (`adapters/extraction/pymupdf.py`) — `pymupdf4llm.to_markdown`
over a `fitz`-opened stream, offloaded to the anyio worker thread (ADR-007: no
blocking call on an async path). Flat Markdown for now; TOC heading reconstruction
is deferred to the navigate-by-chapters slice. Proven against a real generated PDF
in `tests/integration/`. No import-linter change (`adapters` already admitted).

---

## Consequences

- The full status machine now runs end to end against real extraction, and the
  extracted text exists for summarization to consume — keyed by `content_key`,
  never in the database, never on the wire.
- Extraction is independently callable; wiring it to run as a background job on
  upload (and bounding its concurrency) is the next slice, not this one.
- PyMuPDF is in-process — no OCR, no service to run — but a scanned/image-only PDF
  yields little text; acceptable for the text-PDF target, revisited if needed.
