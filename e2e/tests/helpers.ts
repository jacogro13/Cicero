import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, type APIRequestContext } from "@playwright/test";

// The committed sample PDF (ADR-025): a table of contents of two H1 bookmarks,
// so extraction yields the "Alpha" and "Beta" chapters the reader navigates.
const SAMPLE_PDF_PATH = fileURLToPath(
  new URL("../fixtures/sample.pdf", import.meta.url),
);

export const samplePdf = () => ({
  name: "sample.pdf",
  mimeType: "application/pdf",
  buffer: readFileSync(SAMPLE_PDF_PATH),
});

// A per-test title so specs assert on their own document — compose volumes
// persist between runs, so the library is never assumed empty (ADR-025).
export const uniqueTitle = (prefix: string) =>
  `${prefix} ${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

interface DocumentResponse {
  id: string;
  title: string;
  status: string;
}

// Upload straight over the public /api contract (still black-box) — used to seed
// the reader specs, which are about reading, not the admin upload UI.
export async function uploadDocument(
  request: APIRequestContext,
  title: string,
): Promise<string> {
  const response = await request.post("/api/documents", {
    multipart: { title, file: samplePdf() },
  });
  expect(response.ok()).toBeTruthy();
  const doc = (await response.json()) as DocumentResponse;
  return doc.id;
}

// Poll the read side until the document is summarised — the pipeline is serial,
// so this is upload → extract → summarise completing behind the single worker.
export async function waitForSummarised(
  request: APIRequestContext,
  id: string,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await request.get(`/api/documents/${id}/summary`);
        return response.status();
      },
      { timeout: 60_000, intervals: [1000] },
    )
    .toBe(200);
}
