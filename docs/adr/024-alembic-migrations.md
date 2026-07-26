# ADR-024: Alembic Migrations Replace Startup `create_all`

**Status:** Accepted

> Supersedes the startup-provisioning decision of
> [ADR-010](010-composition-root-settings-and-startup-provisioning.md), which deferred
> Alembic with an explicit trigger: "revisit when the schema must evolve under real data."
> That trigger has fired.

---

## Context

ADR-010 provisioned the schema with `metadata.create_all` — create-only, it never
alters an existing table. [ADR-021](021-chapters-from-the-pdf-table-of-contents.md)
reshaped `summaries` (added `position`, made the key composite). Against a fresh DB
`create_all` builds the new shape; against a **persistent volume** it left the old
table untouched, so a running dev stack raised `column summaries.position does not
exist` — the `/chapters` read 500'd and per-chapter writes could not land. Patching
dev by hand masked a systemic gap: every further schema-changing stage (#17 kind, #18
enrichment, #21 vectors) repeats it. The schema now evolves under real data.

---

## Decision

**`alembic upgrade head` replaces `create_all` at startup.** `provision_infrastructure`
runs migrations to head instead of `create_all`; the bucket step is unchanged. Turnkey
`docker compose up` survives — migrations run from the app, no init container.

**One honest baseline (`0001`) = the current schema** — `documents`, `chapters`,
`summaries` (composite `(document_id, position)`), and the `document_status` enum,
exactly as `orm.py` defines it today. The baseline is not split to re-enact ADR-021's
reshape: that reshape already shipped in `orm.py`, there is no production history to
preserve (ADR-010), and inventing a pre-reshape baseline would contradict the code.
The **first real `ALTER` migration lands with #17** (the `kind` column), for real.

**`env.py` targets the async engine + `orm.metadata`** as the autogenerate source, so
a drift between models and migrations is detectable. `start_mappers()` stays the
runtime mapping step, independent of provisioning.

**Provisioned dev DBs:** their live schema already matches `0001`, so `alembic stamp
head` marks them current; a stale volume is dropped (no data to preserve).

---

## Consequences

- Schema changes are now versioned and forward-migrating; the create-only gap that
  broke a persistent volume is closed, and #17/#18/#21 each add an ordered migration.
- `orm.metadata` stays the single schema truth: `0001` mirrors it and `env.py`
  autogenerate diffs against it, so a model change with no migration is caught.
- Integration tests keep building their throwaway schema from `metadata` directly —
  per-test `create_all`/`drop_all` is isolation, not provisioning, and stays fast; a
  dedicated test proves `upgrade head` builds the same schema.
- No `ALTER` is demonstrated until #17 — an accepted cost of not faking history.
