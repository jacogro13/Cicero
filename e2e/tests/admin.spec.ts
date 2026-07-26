import { expect, test } from "@playwright/test";

import { samplePdf, uniqueTitle } from "./helpers";

// The admin console (ADR-017/019): the maintenance surface a reader never sees.
// One spec walks the whole shipped lifecycle through the UI — upload, watch the
// pipeline run, inspect both read views and the source PDF, then delete.
test("upload → summarised → inspect → delete", async ({ page }) => {
  const title = uniqueTitle("Admin E2E");

  await page.goto("/admin");

  // Upload through the form (not the API) — this is the upload UI's coverage.
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("PDF").setInputFiles(samplePdf());
  await page.getByRole("button", { name: "Upload" }).click();

  const row = page.getByRole("listitem").filter({ hasText: title });

  // Poll to the terminal read state: upload → extract → summarise, behind the
  // single serial worker. The badge reads "Summarised" only at the end.
  await expect(row.getByText("Summarised", { exact: true })).toBeVisible({
    timeout: 60_000,
  });

  // The LLM summary read view (mock summarizer → deterministic text, ADR-018).
  await row.getByRole("button", { name: "View summary" }).click();
  const summary = page.getByRole("dialog", { name: `Summary of ${title}` });
  // A chaptered document's summary is its per-chapter summaries concatenated, so
  // the mock text appears once per chapter — assert the first occurrence renders.
  await expect(
    summary.getByText("This is a mock summary of the document.").first(),
  ).toBeVisible();
  await summary.getByRole("button", { name: "Close" }).click();
  await expect(summary).toBeHidden();

  // The extracted-Markdown read view — admin-only, the internal text a reader
  // never sees (ADR-019); the fixture's first chapter body proves real extraction.
  await row.getByRole("button", { name: "View extracted" }).click();
  const extracted = page.getByRole("dialog", {
    name: `Extracted text of ${title}`,
  });
  await expect(extracted.getByText(/Alpha body/)).toBeVisible();
  await extracted.getByRole("button", { name: "Close" }).click();
  await expect(extracted).toBeHidden();

  // The source PDF streams from object storage as application/pdf — assert the
  // same-origin link resolves rather than opening the browser viewer.
  const pdfHref = await row
    .getByRole("link", { name: "View PDF" })
    .getAttribute("href");
  expect(pdfHref).toBeTruthy();
  const pdf = await page.request.get(pdfHref!);
  expect(pdf.ok()).toBeTruthy();
  expect(pdf.headers()["content-type"]).toContain("application/pdf");

  // Delete tears the document down; the row leaves the list.
  await row.getByRole("button", { name: "Delete" }).click();
  await expect(row).toHaveCount(0);
});
