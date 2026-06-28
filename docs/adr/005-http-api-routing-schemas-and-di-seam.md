# ADR-005: HTTP API — Routing, Schemas, and the Dependency-Injection Seam

**Status:** Accepted

> Builds on [ADR-001](001-hexagonal-ddd-layering.md) (`entrypoints` is the
> outermost layer, importing `services` and `domain`) and
> [ADR-004](004-object-storage-port-and-services-layer.md) (the use cases the
> routes drive). First HTTP surface beyond the `/health` probe.

---

## Context

`UploadDocument` and `ListDocuments` exist as infrastructure-free use cases. They
now need an HTTP surface: a client must `POST` a file to create a document and `GET`
the library list. Three questions precede the route code:

1. How are routes organised and addressed?
2. What crosses the wire — and what must not?
3. The use cases need a `uow_factory` and storage, but the real Postgres/S3
   adapters don't exist yet. How do routes obtain their dependencies, and how is
   the HTTP layer tested before any adapter exists?

---

## Decision

**Routing.** One `APIRouter` per aggregate (`routers/documents.py`,
`prefix="/documents"`), mounted by `create_app` under `/api` → `/api/documents`.
`/health` stays unprefixed (infra probe, not the API). `POST` returns 201, `GET`
returns 200 with a list. The read/write router split arrives with the
two-frontend distinction, not before.

**Schemas (`entrypoints/schemas.py`).** A Pydantic `DocumentResponse` is the wire
shape — `id`, `title`, `status` — built via `from_domain(document)`. It
deliberately omits `content_key`/`source_key`: storage layout is internal and the
extracted text is never shown to the reader (scope). The domain entity never
crosses the entrypoints boundary unmapped.

**Upload transport.** `POST /api/documents` is `multipart/form-data`: a `title`
form field plus an `UploadFile`. The route reads the bytes and calls
`UploadDocument.execute(title, content)` — transport parsing only, no domain logic.

**DI seam (`entrypoints/dependencies.py`).** Provider functions wire the use cases:
`get_upload_document` / `get_list_documents` depend (via `Depends`) on
`get_uow_factory` and `get_document_storage`. Those two **infra providers raise
`NotImplementedError`** until their adapters land. **Tests inject the
in-memory fakes through `app.dependency_overrides`** — FastAPI's seam — so the
route + schema wiring is verified now, and the same routes re-verify unchanged
against real Postgres/storage when the adapters arrive.

No `adapters/` layer is introduced, so the import-linter contract is unchanged
(`entrypoints → services → domain`).

---

## Consequences

- The HTTP layer is thin and testable today: an API test drives the real routes
  with fakes — no Docker, no adapter. The transport boundary stays "parse request,
  call use case, map to schema".
- `DocumentResponse` is the single place the wire shape is defined, keeping
  internal keys and the extracted text off the API by construction.
- Cost: hitting a route without overriding the infra providers raises 500 until
  the adapters land — an explicit "not wired yet" rather than a fake silently
  shipping to production. The real-adapter wiring (and its integration test) is
  the next slice.
