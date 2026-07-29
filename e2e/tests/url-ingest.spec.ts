import { expect, test } from "@playwright/test";

import {
  deleteDocument,
  findDocumentBySourceUrl,
  uniqueArticleUrl,
  waitForAuthors,
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

  // The byline comes from the page's structured metadata, not the body: the mock
  // inferer returns nothing, so a populated author proves the URL branch reads the
  // article:author/published_time tags first (ADR-028 amendment).
  const enriched = await waitForAuthors(request, doc.id);
  expect(enriched.authors).toBe("Alan Kay");
  expect(enriched.year).toBe(2021);

  // The admin row links out to the article, not to a dead "View PDF": a URL
  // document has no source blob, so a /file link would 404 (ADR-027).
  await page.goto("/admin");
  const articleLink = page.locator(`a[href="${url}"]`);
  await expect(articleLink).toBeVisible();
  await expect(articleLink).toHaveText("Visit article");
  await expect(
    page.locator(`a[href="/api/documents/${doc.id}/file"]`),
  ).toHaveCount(0);

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
