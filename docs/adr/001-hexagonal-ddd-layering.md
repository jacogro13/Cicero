# ADR-001: Hexagonal / DDD Layering with a src-layout

**Status:** Accepted

---

## Context

Cicero touches a database, object storage, and an LLM — none of which is the
*point*. The point is the domain: what a document is, the states it moves
through, and its rules. Writing domain logic directly against FastAPI requests
and SQLAlchemy sessions makes every rule slow to test (a database must run) and
hard to reason about, and lets the framework dictate the business rules. We want
the opposite: a pure-Python domain tested in milliseconds, with infrastructure a
swappable detail behind it.

---

## Decision

Adopt **ports-and-adapters (hexagonal) / DDD layering**, dependencies pointing
strictly inward:

```
domain  ←  services  ←  adapters / entrypoints
```

- **`domain/`** — entities, value objects, and the **ports** (abstract
  interfaces) they depend on; pure Python, no framework/DB/HTTP imports.
  `Document` is the **aggregate root** — the only sanctioned entry point for
  change, so it enforces its own invariants.
- **`services/`** — one use-case class per command, taking its dependencies
  (`uow_factory`, storage, …) as **constructor parameters** (no globals); a use
  case owns its transaction via a Unit of Work.
- **`adapters/`** — implement the domain ports against real infrastructure
  (Postgres, S3, an LLM); the only layer that knows those technologies.
- **`entrypoints/`** — inbound side: the FastAPI app, routes, schemas, wiring.

**The import rule is the invariant:** outer imports inner, never the reverse;
adapters depend on ports *defined in the domain*. The language won't enforce it,
so an **import-linter** contract (`pyproject.toml`) checks it in CI via
`make lint`, listing only the layers that exist and growing as they land.

**Packaging:** a **src-layout** (`src/cicero/`) forces tests to import the
*installed* package, so the test environment matches what ships.

Only the layers a capability needs are materialized; the structure grows
just-in-time (today: `domain/` + `entrypoints/`).

---

## Consequences

- Domain rules test as pure functions with fakes — fast, no Docker — and the same
  use case runs against fakes in unit tests and real Postgres/S3 in integration
  tests, behaviour unchanged.
- Wiring is explicit: collaborators arrive as constructor arguments, visible in
  one place, never reached for as globals.
- The cost is indirection (a port + an adapter where a direct call would do) and a
  layering rule the language won't enforce — paid down by the import-linter
  contract. This is the foundation every later ADR builds on, hence recorded first.
