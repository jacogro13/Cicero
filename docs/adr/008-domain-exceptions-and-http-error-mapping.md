# ADR-008: Domain Exceptions and Domain→HTTP Error Mapping

**Status:** Accepted

> Builds on [ADR-001](001-hexagonal-ddd-layering.md) (HTTP stays out of the
> domain), [ADR-003](003-unit-of-work-and-repository-ports.md) (per-aggregate
> structure), and [ADR-005](005-http-api-routing-schemas-and-di-seam.md) (the
> `entrypoints/` transport boundary).

---

## Context

Deleting a document is the first operation that can fail for a *domain* reason —
the id may not exist — and `Document.create` already rejects an empty title, today
with a bare `ValueError`. Two questions follow: how does the domain signal such
failures without naming an HTTP status (ADR-001 keeps transport out of the domain),
and how does the HTTP layer turn them into the right response?

---

## Decision

**A `DomainError` base** (`domain/exceptions.py`), with aggregate-specific
subclasses alongside the aggregate — `InvalidDocumentTitle`, `DocumentNotFound`
(`domain/document/exceptions.py`) — mirroring the per-aggregate ports split
(ADR-003). The domain **raises**; it never imports a status code. `Document.create`
is retrofitted to raise `InvalidDocumentTitle` (was `ValueError`), and the new
`DeleteDocument` use case raises `DocumentNotFound` when `find_by_id` is empty.

**The mapping lives in `entrypoints/`** (`errors.py`): a single registry
`{InvalidDocumentTitle: 422, DocumentNotFound: 404}` and one handler — registered
on the app for the `DomainError` base — that renders `{"detail": str(exc)}` with
the mapped status. A `DomainError` with no registry entry is **re-raised → 500**:
an unmapped domain error is a programming oversight, not a client error.

**Status choices.** `DocumentNotFound` → **404** (the addressed resource is
absent). `InvalidDocumentTitle` → **422** (the request was well-formed but a field
is semantically invalid — the status FastAPI already uses for schema validation,
distinct from a 400 transport error).

No new layer is introduced, so the import-linter contract is unchanged.

---

## Consequences

- HTTP stays out of the domain: the same error maps identically whether raised from
  a route, a CLI, or a background job, and the registry is the one place status
  codes live.
- Adding a domain failure is one subclass + one registry row + the raise site.
- Cost: an unmapped `DomainError` surfaces as 500 by design — an explicit "this
  error was never assigned a client meaning" rather than a silently wrong status.

---

## Note (later): ports declare their failures here too

**A port's failures belong to the port.** `ArticleExtractor` promised "raises on a
failed fetch" while the only type lived in the trafilatura adapter — uncatchable
without an `adapters` import the layering forbids. `DocumentStorage.get` named no
failure at all, and the S3 adapter raised `ClientError` where the double raised
`KeyError`. Both now sit in `domain/document/exceptions.py` as
`ArticleExtractionFailed` and `BlobNotFound`, raised by every implementation and named
in the port's docstring. Neither is registered — the first only reaches a background
stage, the second means metadata points at a missing blob, which is what the
unmapped→500 clause above is for. The handlers keep their broad `except`, now on its
real footing: ADR-009/028 make status the outcome, so *every* failure marks FAILED.

**An empty projection is not an absent document.** Read models keyed by id answer "no
rows" for an id that never existed, so `GET /documents/{unknown}/chapters` returned
`200 []`. Per-document reads now load the aggregate through one `_require_document`
first, leaving the route's 404 its narrower meaning: the document exists, this
artefact is not ready yet.
