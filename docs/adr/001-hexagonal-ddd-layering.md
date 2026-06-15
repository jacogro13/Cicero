# ADR-001: Hexagonal / DDD Layering with a src-layout

**Status:** Accepted

---

## Context

PageMaster is a library application: it ingests documents, extracts and stores
their content, and serves them over HTTP. That work touches several pieces of
infrastructure — a relational database, object storage, an LLM endpoint — none
of which is the *point* of the application. The point is the domain: what a
document is, the states it moves through, and the rules that govern it.

If the domain logic is written directly against FastAPI request objects and
SQLAlchemy sessions, every domain rule becomes expensive to test (a database
must be running) and impossible to reason about in isolation. The framework and
the database end up dictating the shape of the business rules, rather than the
other way around.

We want the opposite: a domain model that is pure Python, tested in
milliseconds with no infrastructure, and infrastructure that is a swappable
detail behind it.

---

## Decision

Adopt a **ports-and-adapters (hexagonal) / DDD layering**, with dependencies
pointing strictly inward:

```
domain  ←  services  ←  adapters / entrypoints
```

- **`domain/`** — Pure Python entities, value objects (e.g. `Document`,
  `DocumentId`, `DocumentStatus`), and the **ports** (abstract interfaces) they
  depend on. No framework, database, or HTTP imports. `Document` is the
  **aggregate root**: the consistency boundary through which every mutation
  passes, so it can enforce its own invariants (e.g. that a document's content
  key is set atomically when it becomes readable). It is a single-entity
  aggregate today; the root is still the only sanctioned entry point for change.
- **`services/`** — One use-case class per command (`UploadDocument`,
  `ListDocuments`, …). Each takes its dependencies (a `uow_factory`, storage,
  extractor, …) as **constructor parameters** — no hidden globals, no
  module-level singletons. Use cases own their transaction scope via a
  **Unit of Work** (`async with uow_factory() as uow:`); one such block commits
  a single aggregate's changes as one transaction — the aggregate is the unit of
  consistency.
- **`adapters/`** — Outbound adapters that implement the domain ports against
  real infrastructure (Postgres, S3, an OpenAI-compatible LLM). The only layer
  that knows about those technologies.
- **`entrypoints/`** — Inbound adapters: the FastAPI app, routes, schemas, and
  dependency wiring.

**The import rule is the invariant:** outer layers import inner ones, never the
reverse. `domain/` and `services/` must never import from `adapters/` or
`entrypoints/`. Adapters depend on ports *defined in the domain*.

**Packaging:** a **src-layout** — the package lives under `src/pagemaster/`, not
at the repo root. This forces the tests to import the *installed* package rather
than accidentally picking up the source tree on `sys.path`, so the test
environment matches what ships.

Only the layers a capability actually needs are materialized; the structure
grows just-in-time. At the time of this ADR only `domain/` and `entrypoints/`
exist — `services/` and `adapters/` are introduced as the first use case and
the first real adapter arrive.

---

## Consequences

**Benefits:**

- Domain rules are tested as pure functions with fakes — fast, deterministic,
  no Docker. A rule like the document's status state machine is a unit test that
  runs in microseconds.
- Infrastructure is swappable behaviour. The same use case is exercised against
  in-memory fakes in unit tests and against real Postgres/S3 in integration
  tests, with the business behaviour unchanged.
- Dependencies are explicit. Because services receive their collaborators as
  constructor arguments, wiring is visible in one place and nothing reaches for
  a global.

**Costs:**

- More indirection than a flat script-style app: a port and an adapter where a
  direct call would do. Justified by testability and the ability to swap the
  mock LLM/storage for real ones.
- The import rule is a convention the layering depends on. It is not enforced by
  the language, so it is enforced mechanically by an **import-linter** contract
  (`[tool.importlinter]` in `pyproject.toml`) run in CI via `make lint`: inner
  layers (`domain`, later `services`) must not import outer ones (`adapters`,
  `entrypoints`). The contract lists only the layers that exist today and grows
  as the others are introduced.

The layering is the foundation every later ADR builds on, which is why it is
recorded first.
