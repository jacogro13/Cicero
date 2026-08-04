import { expect, test } from "@playwright/test";

import { deleteDocument, uniqueTitle, uploadDocument } from "./helpers";

// The document this spec corrects; the afterEach deletes it so it never outlives the run.
let createdId: string | undefined;

test.afterEach(async ({ request }) => {
  if (createdId) {
    await deleteDocument(request, createdId);
    createdId = undefined;
  }
});

// Kind correction (ADR-026): the ingest default is derived from the source, so a PDF
// always lands as a BOOK. Correcting it in the admin console is the only way to move
// the document to the reader's other shelf — that whole loop, black-box.
test("admin kind correction → reader Articles tab", async ({
  page,
  request,
}) => {
  const title = uniqueTitle("Kind E2E");
  // Seeded over /api — this spec is about the correction UI, not the upload UI.
  createdId = await uploadDocument(request, title);

  await page.goto("/admin");
  const row = page.getByRole("listitem").filter({ hasText: title });
  const kind = row.getByRole("group", { name: `Kind of ${title}` });

  // A PDF upload starts on the Books shelf.
  await expect(kind.getByRole("button", { name: "Book" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await kind.getByRole("button", { name: "Article" }).click();

  // The refetched row reflects the stored kind, so this asserts the PATCH landed.
  await expect(kind.getByRole("button", { name: "Article" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // The reader honours the correction: gone from Books, present under Articles.
  await page.goto("/");
  const card = page.locator(`a[href="/documents/${createdId}"]`);
  await expect(page.getByRole("button", { name: "Articles" })).toBeVisible();
  await expect(card).toHaveCount(0);

  await page.getByRole("button", { name: "Articles" }).click();
  await expect(card).toBeVisible();
});
