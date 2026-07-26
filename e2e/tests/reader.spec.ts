import { expect, test } from "@playwright/test";

import { uniqueTitle, uploadDocument, waitForSummarised } from "./helpers";

// The reader (ADR-021/022): the daily read experience. One journey covers both
// shipped surfaces — the library grid lists the document, and its page navigates
// chapters by the table of contents, each showing its per-chapter summary. The
// document is seeded over /api (still black-box); reading, not upload, is the point.
test("library grid → chapter navigation → per-chapter summary", async ({
  page,
  request,
}) => {
  const title = uniqueTitle("Reader E2E");
  const id = await uploadDocument(request, title);
  await waitForSummarised(request, id);

  // The library grid lists the document as a card into the reader.
  await page.goto("/");
  const card = page.getByRole("link", { name: new RegExp(title) });
  await expect(card).toBeVisible();

  await card.click();
  await expect(page).toHaveURL(new RegExp(`/documents/${id}$`));
  await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();

  // The table of contents is the fixture's two H1 bookmarks (ADR-021).
  const toc = page.getByRole("navigation", { name: "Table of contents" });
  await expect(toc.getByRole("button", { name: "Alpha" })).toBeVisible();
  await expect(toc.getByRole("button", { name: "Beta" })).toBeVisible();

  // The first chapter is open by default; its per-chapter summary renders (mock
  // summarizer → deterministic text, ADR-018).
  await expect(page.getByRole("heading", { name: "Alpha", level: 2 })).toBeVisible();
  await expect(
    page.getByText("This is a mock summary of the document."),
  ).toBeVisible();

  // Navigating the TOC swaps in the other chapter and its summary.
  await toc.getByRole("button", { name: "Beta" }).click();
  await expect(page.getByRole("heading", { name: "Beta", level: 2 })).toBeVisible();
  await expect(
    page.getByText("This is a mock summary of the document."),
  ).toBeVisible();
});
