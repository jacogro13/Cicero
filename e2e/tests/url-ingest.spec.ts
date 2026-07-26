import { expect, test } from "@playwright/test";

import {
  deleteDocument,
  findDocumentBySourceUrl,
  uniqueArticleUrl,
  waitForSummarised,
} from "./helpers";

// The article this spec ingests; the afterEach deletes it so it never outlives the run.
let createdId: string | undefined;

test.afterEach(async ({ request }) => {
  if (createdId) {
    await deleteDocument(request, createdId);
    createdId = undefined;
  }
});

// URL ingest (ADR-027): ingest a web article through the admin URL tab, watch the
// same pipeline carry it to a summary, then read it under the reader's Articles tab
// (ADR-026). The page is served by the compose `article-fixture` service, so the
// fetch is real yet self-contained — no live internet.
test("admin URL ingest → summarised → reader Articles tab", async ({
  page,
  request,
}) => {
  const url = uniqueArticleUrl();

  // Ingest through the admin form's URL tab (not the API) — the ingest UI's coverage.
  await page.goto("/admin");
  await page.getByRole("button", { name: "URL" }).click();
  await page.getByLabel("URL").fill(url);
  await page.getByRole("button", { name: "Ingest" }).click();

  // The document arrives as an ARTICLE over the public contract; then wait out the
  // pipeline — a real fetch of the fixture page → extract → mock summary.
  const doc = await findDocumentBySourceUrl(request, url);
  createdId = doc.id;
  expect(doc.kind).toBe("ARTICLE");
  await waitForSummarised(request, doc.id);

  // The reader keeps articles behind the Articles tab, Books first (ADR-026).
  await page.goto("/");
  const card = page.locator(`a[href="/documents/${doc.id}"]`);
  // Wait for the library to load, then confirm the article is hidden under Books…
  await expect(page.getByRole("button", { name: "Articles" })).toBeVisible();
  await expect(card).toHaveCount(0);

  // …and appears once the reader switches to Articles.
  await page.getByRole("button", { name: "Articles" }).click();
  await expect(card).toBeVisible();

  // Opening it renders the article's summary — the whole URL pipeline, end to end
  // (mock summarizer → deterministic text, ADR-018).
  await card.click();
  await expect(page).toHaveURL(new RegExp(`/documents/${doc.id}$`));
  await expect(
    page.getByText("This is a mock summary of the document."),
  ).toBeVisible();
});
