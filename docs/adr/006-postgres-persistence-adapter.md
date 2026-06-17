# ADR-006: Postgres Persistence Adapter (SQLAlchemy + testcontainers)

**Status:** Accepted

> Builds on [ADR-001](001-hexagonal-ddd-layering.md) (layering) and
> [ADR-003](003-unit-of-work-and-repository-ports.md) (the repository + UoW
> ports). Those ports shipped with only an in-memory double and the promise of a
> real Postgres adapter behind them, behaviour re-verified unchanged — this honours it.

---

## Context

The persistence ports exist but nothing real implements them. Standing up Postgres
raises four questions: where concrete adapters live, how the domain model is stored
without the domain knowing SQL (ADR-001), how the adapter is tested for real rather
than mocked, and how the layering fitness function grows to cover it.

---

## Decision

**Introduce the `adapters/` layer** — concrete implementations of domain ports
against real infrastructure, `adapters/persistence/` for the SQLAlchemy pieces. It
is a **sibling of `services/`**: both depend only inward on `domain`, neither imports
the other; composition happens only in `entrypoints`. The import-linter contract
grows to enforce that (adapters independent of services, both above domain).

**SQLAlchemy 2.0 async (asyncpg).** `SqlAlchemyUnitOfWork` wraps an `AsyncSession`
— one `async with` block is one session/transaction, explicit `commit()`, rollback
on any other exit (the ADR-003 contract). `PostgresDocumentRepository` is
`uow.documents` over that session.

**Persistence ignorance via imperative mapping.** The domain `Document` keeps zero
ORM imports; a `Table` + `registry.map_imperatively(Document, …)` declared entirely
in the adapter maps it, with `TypeDecorator`s translating the `DocumentId` value
object ↔ a UUID column and `DocumentStatus` ↔ an enum column. A fetch returns a real
`Document` — no hand-written row↔entity translation to drift.

**Tested against real Postgres via testcontainers** — a throwaway container, not a
mock — in a new **integration** layer (`tests/integration/`, `make integration`)
that re-runs the ADR-003 save/fetch/rollback behaviours unchanged. Schema is built
from the mapped metadata per test for isolation.

**Scope: adapter only.** Wiring the running app to Postgres (settings/`DATABASE_URL`,
engine lifespan, schema/migrations, a compose Postgres service) is deferred to the
composition-root slice alongside object storage; `get_uow_factory` keeps its
`NotImplementedError` seam and API tests still override it with fakes.

---

## Consequences

- One behavioural contract now holds both in-memory and on Postgres; the database
  is a swappable adapter, proven for real rather than mocked.
- Integration tests need a Docker daemon and are slower, so they live under
  `make integration`, out of the fast `make test` loop (CI runs both).
- Imperative mapping keeps the domain pristine but instruments `Document` at runtime
  via a one-time `start_mappers()` — called once in the composition root (idempotent).
- `save` relies on the session identity map (insert / tracked update); detached-object
  update and `delete` arrive with the slices that need them, as the ports did.
