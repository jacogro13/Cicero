# ADR-026: Documents Are Classified as Books or Articles

**Status:** Accepted

---

## Context

Every document has been treated identically: one flat library grid, one "book"
vocabulary throughout the reader. But the corpus is really two kinds of thing —
book-length works (PDF uploads) and shorter web pieces (web-article ingests,
landing alongside this label). Mixing them in one grid makes the reading surface
noisy: a shelf of books is buried under captured articles, and vice-versa. A
cheap, source-derived label lets the reader keep them apart.

---

## Decision

Give each document a **`kind`**: `BOOK` or `ARTICLE`. It is a **browsing
classification only** — it does *not* branch extraction, summarization, or any
pipeline stage; nothing in `NEXT_COMMAND` reads it. One new non-null column
`documents.kind`, mapped imperatively like every other field.

**The default derives from the source at ingest:** PDF uploads → `BOOK`; URL
ingests → `ARTICLE`. The field is overridable at ingest and correctable later;
those write paths are out of scope for this decision.

**First real `ALTER` migration (`0002`).** `ADD COLUMN kind ... NOT NULL` with a
**`server_default` of `BOOK`** so the column is backfilled on existing rows in
one statement — the create-only gap ADR-024 closed, now exercised for real. A
new `document_kind` Postgres enum carries the two values. The ORM column mirrors
the `server_default`, so `Document.create` need not set `kind` for the DB to be
satisfied, and a fresh `upgrade head` and an in-place `ALTER` reach the same
schema.

**Reader presentation** — a Books | Articles switch above the grid — builds on
this column; the wire contract exposes `kind` on `DocumentResponse`.

---

## Consequences

- Cheap, reversible model: a plain enum column with a source-derived default and
  no processing-path branch; `kind` can be wrong without breaking anything.
- `server_default = BOOK` is deliberate belt-and-braces — the app always sends a
  value, but the default keeps the `ALTER` total over pre-existing rows and lets
  a bare `INSERT` (a migration test, a psql poke) stay legal.
- The reader's "book" language becomes partly a misnomer for articles; UI copy is
  made kind-aware where it shows, but component names need not churn.
