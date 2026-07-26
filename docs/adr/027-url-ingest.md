# ADR-027: Ingesting a Web Article by URL

**Status:** Accepted

---

## Context

Ingest has been PDF-only: a multipart upload stores a source blob that the
pipeline extracts. But a large part of the corpus is web articles, which have no
file to upload — only a link. We want the *same* read experience for them (an
AI summary), reusing the extract → summarise pipeline rather than a parallel one.
A URL, though, is a different kind of source: nothing to store up front, and the
"extract" step is fetch-and-parse-HTML, not render-a-PDF.

---

## Decision

**`POST /api/documents/url` with `{"url": ...}`** issues an `IngestUrl` command
and echoes a `DocumentResponse` (kind `ARTICLE`, status `UPLOADED`), then the
existing pipeline advances it — no new conveyor.

**The URL is the source.** A URL document stores no blob at ingest; instead the
aggregate carries a nullable **`source_url`**. `Document.create_from_url(url)`
validates the scheme (http/https, else `InvalidDocumentUrl` → 422), derives an
initial title from the URL, and sets `kind = ARTICLE`. The real fetch is deferred
to the worker, so ingest stays fast and a fetch failure lands in the normal
`FAILED` terminal, not on the request path.

**Processing branches on the source, never on `kind`.** ADR-026 keeps `kind` a
browsing label no stage reads; the processing discriminator is `source_url`.
`ExtractDocument` branches: a URL source is fetched and parsed into a **single
`Chapter`** via a new **`ArticleExtractor`** port (title + Markdown body),
`TrafilaturaArticleExtractor` behind it; a blob source takes the existing PyMuPDF
path. Everything downstream — the chapter blob, titles, transitions, delete-mid-
pipeline guards, the per-chapter summary — is **shared**: an article is just a
one-chapter document, so the reader, summaries, and later RAG reuse it for free.

**Migration `0003`** adds `source_url` (nullable) — the second real `ALTER`.

---

## Consequences

- One pipeline, two sources: modelling an article as a single-chapter document
  means no read model, summary path, or reader view has to special-case it.
- `kind` and `source_url` stay orthogonal — a mis-set `kind` can never mis-route
  processing, and correcting it later touches nothing in the pipeline.
- The fetch reaches the network at *extraction* time inside the worker; the
  trafilatura adapter is offloaded to a thread like PyMuPDF (ADR-007).
- "View original" for an article is the link, not a stored blob, so `/file` has
  nothing to stream for URL documents — the reader opens `source_url` instead.
