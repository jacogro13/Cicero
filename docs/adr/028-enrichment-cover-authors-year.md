# ADR-028: Enrichment — Cover, Authors, Year

**Status:** Accepted

---

## Context

The library grid shows only a title and a status badge; a real shelf shows
covers and attribution. We want each document to grow a **cover image**,
**author(s)**, and a **year** — none essential to *reading*, which is done the
moment a document is `SUMMARISED`.

This is the first stage **not on the readability spine**. `DocumentStatus` has
been a forward-only line ending at `SUMMARISED`; enrichment cannot join it —
before `SUMMARISED` it would delay readability, after it would reopen a "done"
document. It is a branch.

---

## Decision

**`DocumentStatus` stays the linear readability spine** (`UPLOADED → … →
SUMMARISED`); enrichment never touches it, carrying its **own per-artifact
status** `EnrichmentStatus` (`PENDING → ENRICHED / FAILED`). A `FAILED` enrichment
leaves the document fully readable — best-effort, never a gate. First per-artifact
status; later best-effort stages reuse the shape.

**A second, dedicated job queue** carries the branch off the request path.
`ExtractionCompleted` — where both source blob and extracted text exist — gets a
**second subscriber** enqueuing the id onto it (the existing re-enqueue handler, a
different queue). That queue's consumer reads `enrichment_status` and dispatches
`EnrichDocument` while `PENDING`, so the "edge derives the command from persisted
status" rule holds on the enrichment axis and restart recovery re-enqueues
`PENDING` documents with no special case.

**`EnrichDocument`** is best-effort: `PENDING → ENRICHING (transient) → ENRICHED`,
or `→ FAILED` on any error, never raising past the worker. It fills three things:

- **Cover** — a PDF's page 0 rendered to PNG via a `CoverRenderer` port (PyMuPDF);
  an article's `og:image`, **not a screenshot**, via an `ArticleCoverRenderer` port
  (trafilatura reads the tag from HTML, one scheme-checked, size/type-capped `httpx`
  GET pulls the bytes — no headless browser). Stored at `cover_key`, absent when
  neither yields an image. A server-side render is a possible later upgrade.
- **Authors / year** — a `MetadataInferer` port over the opening extracted text
  (`MockMetadataInferer` the zero-config default, an OpenAI-compatible adapter when
  `LLM_BASE_URL` is set), with a **docinfo fallback** for PDFs: the file's own
  author/date, harvested with the cover, fills what the model leaves blank.

Persisted on `documents` (migration `0004`): `authors` (text, null), `year` (int,
null), `has_cover` (bool), `enrichment_status`. The cover is a blob under the
document's key prefix, so delete sweeps it. A new read view backs
`GET /documents/{id}/cover` (404 until rendered); the list view and the reader
grid grow covers and attribution.

---

## Consequences

- The pipeline is now a spine plus a branch. `DocumentStatus` means *readable*;
  enrichment progress is a separate axis nothing on the spine reads.
- Two queues give the branch its own concurrency budget — a slow cover render
  cannot starve summarization, and vice versa.
- Enrichment is idempotent: re-running overwrites, so a retried job is safe; a
  screenshot cover for pages without an `og:image` remains a future upgrade.
