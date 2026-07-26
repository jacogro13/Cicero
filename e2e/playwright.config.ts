import { defineConfig, devices } from "@playwright/test";

// Black-box E2E against the real compose stack (ADR-025): a browser hits the
// `web` service, which proxies same-origin /api to the api, over real Postgres
// + MinIO. Nothing here imports frontend/ or src/ — it knows only URLs.
const WEB_PORT = process.env.WEB_HOST_PORT ?? "5173";
const BASE_URL = `http://localhost:${WEB_PORT}`;

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
  // `article-fixture` service the URL-ingest spec fetches (ADR-027).
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
    env: { LLM_BASE_URL: "" },
  },
});
