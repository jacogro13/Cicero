import { defineConfig, devices } from "@playwright/test";

// Black-box E2E against the real compose stack (ADR-025): a browser hits the
// `web` service, which proxies same-origin /api to the api, over real Postgres
// + MinIO. Nothing here imports frontend/ or src/ — it knows only URLs.
//
// The stack runs as its own compose project (`cicero-e2e`) on its own host ports,
// so it gets its own postgres_data/minio_data volumes and never touches the library
// a plain `docker compose up` (project `cicero`) serves — E2E documents stay out of
// the dev stack. Tear it down with `make e2e-down`.
const COMPOSE_PROJECT_NAME = "cicero-e2e";
const WEB_HOST_PORT = process.env.WEB_HOST_PORT ?? "5273";
const API_HOST_PORT = "8100";
const DB_HOST_PORT = "5533";
const MINIO_HOST_PORT = "9100";
const MINIO_CONSOLE_HOST_PORT = "9101";
const BASE_URL = `http://localhost:${WEB_HOST_PORT}`;

export default defineConfig({
  testDir: "./tests",
  // The pipeline (extract → summarise) runs after upload, so flows wait on
  // polled UI; give each spec room without masking a genuine hang.
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  // One retry in CI absorbs a cold-stack timing blip; locally a failure is a failure.
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  // Bring the whole stack up from the repo root (reusing one already running),
  // forcing the mock summarizer so summaries are deterministic regardless of a
  // local .env pointing LLM_BASE_URL at a real endpoint. The `e2e` profile adds the
  // `article-fixture` service the URL-ingest spec fetches (ADR-027). COMPOSE_PROJECT_NAME
  // + the *_HOST_PORT overrides give this its own volumes and ports, isolating it from a
  // dev `docker compose up` — reuseExistingServer only ever matches another e2e stack.
  webServer: {
    command: "docker compose --profile e2e up --build",
    cwd: "..",
    // Probe the proxied API, not the static shell: nginx serves the SPA the moment
    // it starts, but the api is still building + running startup migrations behind
    // it. GET /api/documents returns 200 only once the whole web→api chain is up.
    url: `${BASE_URL}/api/documents`,
    reuseExistingServer: !process.env.CI,
    // Generous: in CI this cold-builds the api image (pymupdf/onnxruntime) from scratch.
    timeout: 600_000,
    env: {
      LLM_BASE_URL: "",
      COMPOSE_PROJECT_NAME,
      WEB_HOST_PORT,
      API_HOST_PORT,
      DB_HOST_PORT,
      MINIO_HOST_PORT,
      MINIO_CONSOLE_HOST_PORT,
    },
  },
});
