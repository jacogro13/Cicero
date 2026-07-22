# ADR-019: Admin Content Viewers — Storage-Backed Reads

**Status:** Accepted

> The first read views that fetch a **blob** through the `DocumentStorage` port
> rather than a Postgres projection, and the point at which "the extracted text is
> internal" is qualified to *internal to readers*.

---

## Context

The read side so far serves projections: the document list and the summary both
read Postgres ([ADR-015](015-cqrs-read-side.md), [ADR-016](016-ai-summaries-and-the-summary-read-model.md)).
Nothing lets an operator inspect the two artefacts that back the pipeline — the
**extracted Markdown** (did extraction produce sane text?) and the **original
PDF** (is this the right source?). Both live in object storage, addressed by
`content_key` / `source_key`, and neither is on the wire today.

---

## Decision

Two admin-only read routes fetch the blob through the **`DocumentStorage`** port:

- `GET /documents/{id}/content` → the extracted Markdown as `text/markdown`,
  available once the document is `EXTRACTED` (its `content_key` is written then);
  `None` → **404** before that, `DocumentNotFound` → **404** for an unknown id.
- `GET /documents/{id}/file` → the original PDF as `application/pdf`, available
  from `UPLOADED` (the source is stored at upload); **404** only for an unknown id.

The views (`views.get_document_content` / `get_document_file`) load the aggregate
for its status and key, then read the blob — off the injected `uow_factory` **and**
a re-introduced read-side `get_document_storage` seam, still bypassing the bus.
The blobs stay **off the list DTO**: `DocumentResponse` keeps omitting keys and
text. The admin SPA gains a "View extracted" modal and a "View PDF" link, mirroring
the summary modal.

**"Extracted text is internal" becomes reader-scoped.** The reader still never
sees the extracted Markdown — the summary is their read experience. The admin
console *can*, for verification. Architecture's "never displayed" line is qualified
to "never displayed *to readers*".

---

## Consequences

- Establishes the storage-backed read pattern: load the aggregate for its key,
  stream the blob with an honest content-type — reused by any later "download the
  original" / "inspect the intermediate" view.
- The read side now depends on two ports (`uow_factory` + `storage`), so
  `get_document_storage` returns as a leaf seam tests override alongside the bus's
  storage (one shared fake, so an uploaded blob is visible to the read side).
- Serving raw blobs (not a JSON DTO) keeps these honest downloads; the browser
  renders the PDF natively and the FE renders the Markdown itself.
- No import-linter change: views in `services`, routes in `entrypoints`, port in
  `domain`.
