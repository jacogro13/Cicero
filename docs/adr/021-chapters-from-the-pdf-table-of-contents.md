# ADR-021: Chapters from the PDF Table of Contents

**Status:** Accepted

> Refines extraction ([ADR-009](009-content-extraction-and-the-extract-document-use-case.md))
> to produce structure, and the summary read model
> ([ADR-016](016-ai-summaries-and-the-summary-read-model.md)) to be per-chapter.
> Qualifies the admin content view
> ([ADR-019](019-admin-content-viewers-and-storage-backed-reads.md)).

---

## Context

Summaries are one per document. A book's read experience is per-chapter: a table
of contents you navigate, a summary per chapter. `pymupdf4llm` emits flat Markdown,
and its `#` headings are unreliable, so chapter boundaries must come from the PDF's
own bookmarks (`fitz.get_toc()`), not the text. An article extracted from a URL has
no bookmarks — it is a single chapter.

---

## Decision

**Extraction produces chapters, in one PDF pass.** The `DocumentExtractor` port
returns an ordered `list[Chapter]` (a `Chapter` value object: `title`, `markdown`)
instead of one string. Level-1 `get_toc()` entries mark chapter starts; each
chapter's Markdown is rendered from its page range (`to_markdown(doc, pages=…)`).

**Chapterization is a pure function, not a second stage.**
`chapter_ranges(toc, page_count)` (`domain/document/`) maps bookmark tuples to
ordered page ranges — framework-free and unit-tested, the single-responsibility
split kept distinct from the PyMuPDF rendering. It is *not* a separate pipeline
status: both halves need the same open PDF, so a second stage would re-render the
PDF or fall back to unreliable heading-splitting. One `EXTRACTING` stage, one call.

**No bookmarks → one chapter** spanning the whole document — the same path a
URL-extracted article takes. The model is uniformly "1…N chapters", the article the
degenerate 1, so no `if book` branch ever reaches the summariser or the read side.

**Per-chapter content in object storage; titles in a read model.** Extraction
stores each chapter's Markdown at a domain-derived key
`documents/{id}/chapters/{i}` (the flat `content_key` retires) and the ordered
titles via `uow.chapters` — a `ChapterReadModel`, the twin of `summaries`, written
in the same transaction as `mark_extracted()`.

**Summaries become per-chapter.** `SummariseDocument` loops the chapters,
summarising each; `summaries` is keyed `(document_id, chapter_index)`.
`views.document_toc` serves the ordered titles; the summary read serves per chapter.
The stage machinery is unchanged — still one `SummariseDocument` over the conveyor.

**The admin content view assembles chapters** — `get_document_content` (ADR-019)
joins the per-chapter blobs under their titles, so the admin console is unchanged
and gains headings; extracted text stays reader-invisible (ADR-019 scope kept).

---

## Consequences

- The extractor port signature changed (`extract → list[Chapter]`); the mock and
  the integration test move with it. No new status, command, handler, or
  subscription — chapters ride the existing extract→summarise spine.
- Front matter before the first bookmark joins the first chapter — good enough, and
  moot for the single-chapter fallback.
- `summaries` grew a composite key; the admin `/summary` endpoint returns the
  chapter summaries joined, so the admin summary modal keeps working unchanged.
- Chapter *content* lives in storage (large, like ADR-009), chapter *titles* in a
  table (small, queryable) — the same read/write split as summaries.
