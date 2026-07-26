# E2E tests (Playwright)

Black-box end-to-end tests against the real `docker compose` stack — a browser →
`web`/nginx → same-origin `/api` → api → Postgres + MinIO (ADR-025). Nothing here
imports `frontend/` or `src/`; the tests know only the served URLs and the `/api`
contract.

## Run

```sh
make e2e          # from the repo root
```

That installs the Node deps, downloads the Chromium browser, and runs the suite.
Playwright brings the compose stack up itself (reusing one already running) and
forces `LLM_BASE_URL=""` so summaries use the deterministic mock summarizer — no
live LLM, regardless of a local `.env`.

The suite runs its stack as its own compose project (`cicero-e2e`) on its own host
ports (web `5273`, api `8100`, …), so it gets its own Postgres/MinIO volumes and the
documents it creates never land in the library a plain `docker compose up` serves.
Tear it down with `make e2e-down` (from the repo root).

## What it covers

- **admin** (`/admin`): upload a PDF → poll to `SUMMARISED` → view the summary,
  view the extracted Markdown, resolve the source PDF, delete.
- **reader** (`/`, `/documents/:id`): the library grid lists documents; the reader
  page navigates chapters by the table of contents and renders each per-chapter
  summary.
- **url-ingest** (`/admin` → `/`): ingest a web article by URL through the admin URL
  tab → poll to `SUMMARISED` → read it under the reader's **Articles** tab.

The sample PDF (`fixtures/sample.pdf`) carries a two-bookmark table of contents, so
extraction yields the "Alpha" and "Beta" chapters the reader navigates. The URL spec
fetches `fixtures/article.html`, served **inside the compose network** by the
`article-fixture` service — brought up by the `e2e` compose profile (which Playwright
activates), so the fetch is real yet self-contained, with no live internet. A normal
`docker compose up` never starts that service; if you reuse a stack you started
yourself, bring it up under the same isolated project and ports Playwright expects:
`COMPOSE_PROJECT_NAME=cicero-e2e WEB_HOST_PORT=5273 API_HOST_PORT=8100 DB_HOST_PORT=5533 MINIO_HOST_PORT=9100 MINIO_CONSOLE_HOST_PORT=9101 docker compose --profile e2e up`.

A dedicated CI job runs this same suite on every PR (it lets Playwright cold-build the
compose stack on a GitHub-hosted runner), so E2E gates merges as well as local runs.
