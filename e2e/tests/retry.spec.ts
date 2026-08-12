import { expect, test } from "@playwright/test";

import { deleteDocument, uniqueArticleUrl, waitForFailed } from "./helpers";

// The failed document this spec re-drives; the afterEach deletes it so it never
// outlives the run.
let createdId: string | undefined;

test.afterEach(async ({ request }) => {
  if (createdId) {
    await deleteDocument(request, createdId);
    createdId = undefined;
  }
});

// Retry out of FAILED (ADR-030): nothing re-drives a failed document on its own, so
// the admin button is the only way back onto the pipeline — without it a failure is a
// dead end and the only recovery is delete and re-upload. Seeded by ingesting a URL
// the fixture server does not serve, so extraction fails for real.
test("admin retry re-drives a failed document", async ({ page, request }) => {
  const url = uniqueArticleUrl("missing.html");
  const response = await request.post("/api/documents/url", { data: { url } });
  expect(response.ok()).toBeTruthy();
  createdId = ((await response.json()) as { id: string }).id;

  await waitForFailed(request, createdId);

  await page.goto("/admin");
  // The source URL is unique per run, so its link identifies this spec's row.
  const row = page
    .getByRole("listitem")
    .filter({ has: page.locator(`a[href="${url}"]`) });
  await expect(row.getByText("Failed")).toBeVisible();

  // The button reaches the retry endpoint and the backend accepts the re-drive. The
  // re-run itself is not asserted here: this URL fails every time by construction, so
  // the document returns to FAILED too quickly to observe from the browser.
  const retried = page.waitForResponse(
    (res) =>
      res.url().includes(`/api/documents/${createdId}/retry`) &&
      res.request().method() === "POST",
  );
  await row.getByRole("button", { name: "Retry" }).click();
  expect((await retried).status()).toBe(202);
});
