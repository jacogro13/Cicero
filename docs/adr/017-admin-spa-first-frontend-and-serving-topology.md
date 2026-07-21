# ADR-017: The Admin SPA — First Frontend and its Serving Topology

**Status:** Accepted

> The first user-facing surface. Consumes the CQRS read side of
> [ADR-015](015-cqrs-read-side.md)/[ADR-016](016-ai-summaries-and-the-summary-read-model.md)
> and the upload/delete commands behind
> [ADR-005](005-http-api-routing-schemas-and-di-seam.md)'s HTTP surface; extends the
> compose stack of [ADR-010](010-composition-root-settings-and-startup-provisioning.md).

---

## Context

Everything so far is a backend proven by tests and `curl`; there is no way to
*use* Cicero. The first frontend is an **admin SPA** — upload a document, watch it
move `UPLOADED → … → SUMMARISED`, list, delete (the reader SPA comes later). This
slice also decides, once, how any frontend is built, tested, served, and wired into
CI and compose.

---

## Decision

**A separate `frontend/` tree, not part of the hexagon.** React + TypeScript, built
by **Vite**, tested by **Vitest** + Testing Library, styled with **CSS Modules** (no
UI-framework dependency — the code is the CV signal). import-linter still governs
Python only; the frontend carries its own toolchain and its own CI **node job**
beside the Python one.

**Server state via TanStack Query.** The list is a polled query (`refetchInterval`
while any document is non-terminal, off once all are `SUMMARISED`/`FAILED`); upload
and delete are mutations that invalidate it. This is the idiom for read-side polling
and stands in for the deferred push channel (ADR-013) with client polling for now.

**Topology: a dedicated `web` service serves the build; the api stays slim.** In
production a new **nginx** compose service serves the built assets and
reverse-proxies `/api → api`, so the SPA always calls **same-origin `/api`** — no
CORS on FastAPI, and the api image stays decoupled from the FE build (keeping
ADR-010's image-split direction). In development the **Vite dev server** proxies
`/api → :8000`, same contract. FastAPI does not serve static assets.

**No auth yet.** The admin SPA is unauthenticated — the stack is single-user and
local. Real auth and the reader/admin role split arrive later, a recorded deferral.

**Pragmatic testing.** Component tests exercise the flows (render, upload,
list-refresh, delete) against a mocked client; **no backend-style red→green
ceremony** — the frontend is verified working, not driven test-first.

---

## Consequences

- The repo is now polyglot: a node toolchain and a second CI job join the Python
  ones; `make` gains frontend targets, and `docker compose up` now brings a web UI.
- Same-origin `/api` (nginx in prod, Vite proxy in dev) means the API needs no CORS
  config and the client hardcodes no host — one contract across both environments.
- The first user-facing surface. A `web` image joins the slim api — two build
  artifacts cleanly split, at the cost of one more compose service.
- Client-side polling is a stopgap; a push channel (SSE) can later replace the
  `refetchInterval` without changing the query-shaped UI.
