import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import * as api from "../api/documents";
import { renderWithClient } from "../test-utils";

vi.mock("../api/documents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/documents")>();
  return { ...actual, listDocuments: vi.fn(), getChapters: vi.fn() };
});

const mockedApi = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.listDocuments.mockResolvedValue([
    {
      id: "1",
      title: "The Odyssey",
      status: "SUMMARISED",
      kind: "BOOK",
      authors: null,
      year: null,
      has_cover: false,
    },
  ]);
});

describe("ReaderPage", () => {
  it("navigates chapters by the TOC and reads the chapter summary", async () => {
    const user = userEvent.setup();
    mockedApi.getChapters.mockResolvedValue([
      {
        index: 0,
        title: "Book I",
        summary: "## Athena\n\nThe goddess pleads.",
      },
      { index: 1, title: "Book II", summary: "Telemachus sails at dawn." },
    ]);

    renderWithClient(<App />, "/documents/1");

    // The document title and the first chapter's summary render on arrival…
    expect(
      await screen.findByRole("heading", { name: "The Odyssey" }),
    ).toBeInTheDocument();
    // …as formatted Markdown, not raw text.
    expect(
      await screen.findByRole("heading", { name: "Athena" }),
    ).toBeInTheDocument();

    // Selecting another chapter from the TOC shows its summary.
    await user.click(screen.getByRole("button", { name: "Book II" }));
    expect(
      await screen.findByText("Telemachus sails at dawn."),
    ).toBeInTheDocument();
    expect(mockedApi.getChapters).toHaveBeenCalledWith("1");
  });

  it("marks a chapter awaiting its summary as pending", async () => {
    mockedApi.getChapters.mockResolvedValue([
      { index: 0, title: "Book I", summary: null },
    ]);

    renderWithClient(<App />, "/documents/1");

    expect(
      await screen.findByText(/hasn’t been summarised yet/),
    ).toBeInTheDocument();
  });

  it("shows a not-ready state when the document has no chapters", async () => {
    mockedApi.getChapters.mockResolvedValue([]);

    renderWithClient(<App />, "/documents/1");

    expect(
      await screen.findByText(/isn’t ready to read yet/),
    ).toBeInTheDocument();
  });
});
