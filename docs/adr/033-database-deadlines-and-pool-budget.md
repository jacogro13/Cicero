# ADR-033: Database Deadlines and a Stated Pool Budget

**Status:** Accepted

> Refines the engine of [ADR-006](006-postgres-persistence-adapter.md), owned by the
> composition root of [ADR-010](010-composition-root-settings-and-startup-provisioning.md).

---

## Context

`create_async_engine` was called with `pool_pre_ping` and `pool_recycle` and nothing
else. Everything not named there came from a library default, and two of those defaults
mattered.

asyncpg's `command_timeout` is `None`: **no statement deadline at all**. Every other
client in the process has one — the outbound HTTP adapters set an explicit `httpx.Timeout`
(ADR-018, ADR-028), botocore supplies its own — so the database was the single unbounded
wait left. A query that never returns holds its request, or its queue worker, forever.

The pool numbers were SQLAlchemy's: five connections, ten overflow, a 30s wait for a
free one. Reasonable numbers, but nothing in the code said so, and a pool that fills is
diagnosed by reading the library rather than the app.

---

## Decision

**Every connection carries a statement deadline.** `connect_args` sets asyncpg's
`command_timeout` (30s) and connect `timeout` (10s). Thirty seconds is far above any
statement this app issues — single-row reads and upserts over a personal library — and
far below forever.

**The pool budget is stated rather than inherited.** `pool_size`, `max_overflow`, and
`pool_timeout` are written out next to the concurrency they serve: one uvicorn worker,
its request handlers, and the two queue workers (ADR-013, ADR-028). The numbers match
what SQLAlchemy would have chosen; that they are now visible and tunable is the change.

**A policy value with a default, not new settings.** `EnginePolicy` follows ADR-029's
`RetryPolicy`: a frozen value the tests pin directly, and no environment knob invented
before a deployment needs to move one.

---

## Consequences

- Alembic runs its own engine (ADR-024), so migrations sit outside this deadline
  deliberately — a long `ALTER` on a real table must not be killed at 30s.
- A statement past the deadline raises asyncpg's `TimeoutError`, not a SQLAlchemy
  `DBAPIError`, so anything catching database failures by SQLAlchemy type will miss it.
  Handlers treat an unexpected raise as `FAILED` (ADR-014), which is the right outcome.
- The deadline is per statement, not per transaction or per request. A unit of work that
  issues many statements can still outlive 30s in total; bounding that belongs to the
  caller, not the engine.
- Sizing the pool is now a decision someone can get wrong. It was always one — it was
  just being made by the library.
