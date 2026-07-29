import { expect, test } from "@playwright/test";

import {
  deleteDocument,
  uniqueTitle,
  uploadDocument,
  waitForCover,
} from "./helpers";

// The document this spec seeds; the afterEach deletes it so it never outlives the run.
let createdId: string | undefined;

test.afterEach(async ({ request }) => {
  if (createdId) {
    await deleteDocument(request, createdId);
    createdId = undefined;
  }
});

// Enrichment (ADR-028): the best-effort branch off the readability spine. The sample
// PDF's first page renders to a cover on the enrichment queue, and the reader's shelf
// shows it. Seeded over /api (still black-box); the cover on the grid is the point, so
// the spec waits on the branch's own signal — the cover endpoint — not on summarisation.
test("library shelf shows the enriched cover", async ({ page, request }) => {
  const title = uniqueTitle("Cover E2E");
  const id = await uploadDocument(request, title);
  createdId = id;
  await waitForCover(request, id);

  await page.goto("/");
  const card = page.getByRole("link", { name: new RegExp(title) });
  await expect(card).toBeVisible();

  // The card carries the rendered page-0 cover, addressed by the cover endpoint.
  const cover = card.getByRole("img", { name: new RegExp(`Cover of ${title}`) });
  await expect(cover).toBeVisible();
  await expect(cover).toHaveAttribute("src", `/api/documents/${id}/cover`);
});
