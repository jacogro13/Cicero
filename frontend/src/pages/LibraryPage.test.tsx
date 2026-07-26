import { screen } from "@testing-library/react";
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
});

describe("LibraryPage", () => {
  it("lists documents as cards linking into the reader", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED" },
      { id: "2", title: "Draft notes", status: "EXTRACTING" },
    ]);

    renderWithClient(<App />, "/");

    const link = await screen.findByRole("link", { name: /The Odyssey/ });
    expect(link).toHaveAttribute("href", "/documents/1");
    // A still-processing document appears with its status, not as an error.
    expect(screen.getByText("Extracting")).toBeInTheDocument();
  });

  it("shows an empty state when the library has no documents", async () => {
    mockedApi.listDocuments.mockResolvedValue([]);

    renderWithClient(<App />, "/");

    expect(await screen.findByText(/library is empty/i)).toBeInTheDocument();
  });
});
