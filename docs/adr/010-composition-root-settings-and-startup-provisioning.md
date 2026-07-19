# ADR-010: Composition Root — Settings, Engine Lifespan, and Startup Provisioning

**Status:** Accepted

> Closes the seam left open by [ADR-005](005-http-api-routing-schemas-and-di-seam.md)
> (the `NotImplementedError` infra providers), [ADR-006](006-postgres-persistence-adapter.md)
> ("wiring the running app to Postgres is deferred to a composition-root slice"), and
> [ADR-007](007-s3-object-storage-adapter.md) ("the bucket is provisioned by the
> composition root / compose init"). This is that slice: the app actually runs.

---

## Context

Every adapter exists and is proven against real infra, but nothing wires them to a
running process. The DI providers raise, so the app boots only under test overrides.
Three things are missing: configuration (where the DB URL and S3 credentials come
from), object lifecycle (one engine per process, disposed on shutdown), and
provisioning (the schema and bucket the adapters *assume* exist). And the whole
point — `docker compose up` — needs a stack.

---

## Decision

**Settings via `pydantic-settings`** (`entrypoints/settings.py`) — 12-factor,
env-driven: required `database_url`, `s3_endpoint_url`, `s3_access_key_id`,
`s3_secret_access_key`; defaulted `s3_bucket`, `s3_region`. `get_settings()` is
`lru_cache`d (one read per process). No secrets in code; `.env.example` carries
placeholders.

**The composition root is `entrypoints/dependencies.py`.** It holds a process-wide
async **engine + session factory** (created lazily, disposed on shutdown), builds the
`UnitOfWork` factory and the `S3DocumentStorage` from settings, and so **retires both
`NotImplementedError` seams** — real wiring replaces them. API tests keep overriding
the same providers with fakes (ADR-005), so the fast suite stays infra-free.

**Self-provisioning at startup (FastAPI `lifespan`), idempotent:** create the schema
(`metadata.create_all` + the one-time `start_mappers()`) and ensure the bucket
(`ensure_bucket()`, a provisioning method separate from the put/get/delete data path,
which still *assumes* the bucket — ADR-007). **Alembic migrations are deliberately
deferred:** the app solely owns this schema, there is no production history to
preserve, and `create_all` makes `docker compose up` turnkey with no init container.
Revisit when the schema must evolve under real data.

**Compose stack** (`docker-compose.yml` + `Dockerfile`): Postgres + **MinIO** (the
standard, console-equipped S3 store — same `S3DocumentStorage`) + the api, gated on
service health. `docker compose up` runs the app end to end.

---

## Consequences

- The app boots for real: an integration test drives the live app over real Postgres
  + MinIO with **no `dependency_overrides`**, proving the seams are gone and startup
  provisions both schema and bucket.
- `make dev` now needs the infra (a `docker compose up` away); the fast `make test`
  suite is untouched (it never enters the lifespan).
- The api image carries ~165 MB of extraction stack — pymupdf (81) + onnxruntime (52)
  + numpy (32), pulled in via `pymupdf4llm → pymupdf-layout → onnxruntime`. The fix is
  a slim api image with extraction split into a separate worker image; it waits until
  a worker process exists to split out.
- Schema-at-startup is fine while one app owns the schema; the day it evolves under
  real data, an Alembic baseline replaces `create_all` — a deliberate, recorded debt.
