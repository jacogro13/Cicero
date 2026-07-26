# ADR-025: End-to-End Tests with Playwright

**Status:** Accepted

> Pays the deferred-E2E debt for every frontend flow shipped through
> [ADR-017](017-admin-spa-first-frontend-and-serving-topology.md) (admin) and
> [ADR-022](022-the-reader-spa-and-the-role-split.md) (reader), and sets the cadence
> the later frontend batches follow.

---

## Context

Both SPAs are proven only by component tests against a mocked client (ADR-017): fast,
but nothing exercises the real path a user takes — browser → `web`/nginx →
same-origin `/api` → api → Postgres + MinIO, with the pipeline actually running. The
original plan end-loaded all E2E into the final CI batch; that is the classic
big-bang integration risk, and it leaves every shipped flow uncovered until then.

---

## Decision

**A separate `e2e/` tree, black-box.** Its own Node/Playwright toolchain, no imports
from `frontend/` or `src/` — it knows only the served URLs and the `/api` contract, the
same stance ADR-017 took (frontend outside the hexagon; import-linter is Python-only).

**Tests drive the real `docker compose` stack.** Playwright brings the stack up
(`webServer`, reusing an already-running one) and points a browser at the `web`
service, so a spec runs exactly what `docker compose up` gives a reviewer.

**The mock summarizer, always.** E2E forces `LLM_BASE_URL=""` so summaries are the
deterministic canned text — no live LLM, mirroring the CI stance of
[ADR-018](018-openai-compatible-summarizer-adapter.md). Extraction runs for real
(PyMuPDF over a committed sample PDF).

**Per-slice accrual.** Every frontend-touching batch from #17 ships at least one
black-box spec here; this batch backfills all already-shipped flows (admin: upload →
`SUMMARISED` → summary / extracted / PDF / delete; reader: library grid → chapter
nav → per-chapter summary). This supersedes the end-loaded-E2E plan.

**`make e2e` runs it locally; a dedicated CI job gates every PR.** The job (GitHub-hosted
runner) lets Playwright cold-build the compose stack and run both flows — the full stack
plus a browser is heavy, so it is its own job beside the unit/integration/frontend/image
ones, not folded into them. #25 shrinks to *consolidating* the per-slice specs, no longer
to first wiring E2E into CI.

---

## Consequences

- The first test that proves the nginx proxy, the same-origin contract, and the live
  pipeline end-to-end — the gap component tests structurally cannot cover.
- A binary PDF fixture is committed: the tree is black-box, so it cannot call the
  Python/fitz generator the integration tests use — a tiny fixture is the pragmatic cost.
- Compose volumes persist between runs, so specs assert on their own uniquely-titled
  document, never on global counts or an empty-library state.
- The E2E job cold-builds the api image (pymupdf/onnxruntime) per run, so it is the
  slowest PR job — accepted as the price of gating the real stack; the readiness probe
  and a generous `webServer` timeout absorb the build, one retry absorbs a timing blip.
