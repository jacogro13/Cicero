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
  kind: string;
  source_url: string | null;
  authors: string | null;
  year: number | null;
}

// The self-contained article the compose `article-fixture` service serves (ADR-027):
// reachable only inside the compose network, which is where the api fetches it. A
// per-run query string makes each ingest's source_url unique on a persistent volume.
export const uniqueArticleUrl = () =>
  `http://article-fixture/article.html?run=${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;

// Find the ingested document over the public /api contract, by the source_url the
// admin form submitted — the URL path/title is shared across runs, source_url is not.
export async function findDocumentBySourceUrl(
  request: APIRequestContext,
  sourceUrl: string,
): Promise<DocumentResponse> {
  let match: DocumentResponse | undefined;
  await expect
    .poll(
      async () => {
        const response = await request.get("/api/documents");
        const docs = (await response.json()) as DocumentResponse[];
        match = docs.find((doc) => doc.source_url === sourceUrl);
        return match !== undefined;
      },
      { timeout: 30_000, intervals: [500] },
    )
    .toBe(true);
  return match!;
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

// Tear a document down over the public /api contract (still black-box) — specs that
// seed via /api clean up the same way in an afterEach, so no E2E document outlives its
// run even on the isolated stack (ADR-025). Mirrors the admin spec's UI delete.
export async function deleteDocument(
  request: APIRequestContext,
  id: string,
): Promise<void> {
  const response = await request.delete(`/api/documents/${id}`);
  expect(response.status()).toBe(204);
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

// Poll the list read side until enrichment has filled the byline — the branch runs
// off ExtractionCompleted on its own queue (ADR-028), so authors/year land
// independently of summarisation. Returns the enriched document.
export async function waitForAuthors(
  request: APIRequestContext,
  id: string,
): Promise<DocumentResponse> {
  let match: DocumentResponse | undefined;
  await expect
    .poll(
      async () => {
        const response = await request.get("/api/documents");
        const docs = (await response.json()) as DocumentResponse[];
        match = docs.find((doc) => doc.id === id);
        return match?.authors ?? null;
      },
      { timeout: 60_000, intervals: [1000] },
    )
    .not.toBeNull();
  return match!;
}

// Poll until enrichment has rendered a cover — the branch runs off ExtractionCompleted
// on its own queue (ADR-028), so this completes independently of summarisation.
export async function waitForCover(
  request: APIRequestContext,
  id: string,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await request.get(`/api/documents/${id}/cover`);
        return response.status();
      },
      { timeout: 60_000, intervals: [1000] },
    )
    .toBe(200);
}
