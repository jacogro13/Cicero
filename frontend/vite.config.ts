import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev server proxies /api to the api on :8000, so the browser only ever calls
// same-origin /api — the same contract nginx serves in production (ADR-017).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
    css: true,
  },
});
