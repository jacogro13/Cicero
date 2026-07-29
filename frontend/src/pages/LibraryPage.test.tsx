import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import * as api from "../api/documents";
import type { DocumentResponse } from "../api/documents";
import { renderWithClient } from "../test-utils";

vi.mock("../api/documents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/documents")>();
  return { ...actual, listDocuments: vi.fn(), getChapters: vi.fn() };
});

const mockedApi = vi.mocked(api);

// A fully-shaped list entry; specs override only the fields they exercise, so the
// enrichment fields carry their un-filled defaults unless a test fills them.
const doc = (over: Partial<DocumentResponse> = {}): DocumentResponse => ({
  id: "1",
  title: "The Odyssey",
  status: "SUMMARISED",
  kind: "BOOK",
  authors: null,
  year: null,
  has_cover: false,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LibraryPage", () => {
  it("shows books by default and links them into the reader", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      doc({ id: "1", title: "The Odyssey", kind: "BOOK" }),
      doc({ id: "2", title: "A Blog Post", kind: "ARTICLE" }),
    ]);

    renderWithClient(<App />, "/");

    const link = await screen.findByRole("link", { name: /The Odyssey/ });
    expect(link).toHaveAttribute("href", "/documents/1");
    // Articles are hidden until the reader switches to them.
    expect(screen.queryByText("A Blog Post")).not.toBeInTheDocument();
  });

  it("switches to articles, hiding books", async () => {
    const user = userEvent.setup();
    mockedApi.listDocuments.mockResolvedValue([
      doc({ id: "1", title: "The Odyssey", kind: "BOOK" }),
      doc({ id: "2", title: "A Blog Post", kind: "ARTICLE" }),
    ]);

    renderWithClient(<App />, "/");
    await screen.findByText("The Odyssey");

    await user.click(screen.getByRole("button", { name: "Articles" }));

    expect(await screen.findByText("A Blog Post")).toBeInTheDocument();
    expect(screen.queryByText("The Odyssey")).not.toBeInTheDocument();
  });

  it("shows a kind-aware empty state", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      doc({ id: "2", title: "A Blog Post", kind: "ARTICLE" }),
    ]);

    renderWithClient(<App />, "/");

    // Only an article exists, so the default Books grid is empty.
    expect(await screen.findByText("No books yet.")).toBeInTheDocument();
  });

  it("shows an enriched cover and its attribution on the shelf", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      doc({
        id: "7",
        title: "Clean Code",
        authors: "Robert C. Martin",
        year: 2008,
        has_cover: true,
      }),
    ]);

    renderWithClient(<App />, "/");

    const cover = await screen.findByRole("img", {
      name: /Cover of Clean Code/,
    });
    expect(cover).toHaveAttribute("src", "/api/documents/7/cover");
    expect(screen.getByText("Robert C. Martin · 2008")).toBeInTheDocument();
  });

  it("renders no cover image for a document enrichment has not covered", async () => {
    // Enrichment is best-effort, so a book may never get a cover — the card still
    // shows, just without an <img> (ADR-028).
    mockedApi.listDocuments.mockResolvedValue([
      doc({ id: "8", title: "The Odyssey", has_cover: false }),
    ]);

    renderWithClient(<App />, "/");

    await screen.findByText("The Odyssey");
    expect(
      screen.queryByRole("img", { name: /Cover of/ }),
    ).not.toBeInTheDocument();
  });
});
