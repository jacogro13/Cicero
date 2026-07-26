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
});

describe("LibraryPage", () => {
  it("shows books by default and links them into the reader", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED", kind: "BOOK" },
      { id: "2", title: "A Blog Post", status: "SUMMARISED", kind: "ARTICLE" },
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
      { id: "1", title: "The Odyssey", status: "SUMMARISED", kind: "BOOK" },
      { id: "2", title: "A Blog Post", status: "SUMMARISED", kind: "ARTICLE" },
    ]);

    renderWithClient(<App />, "/");
    await screen.findByText("The Odyssey");

    await user.click(screen.getByRole("button", { name: "Articles" }));

    expect(await screen.findByText("A Blog Post")).toBeInTheDocument();
    expect(screen.queryByText("The Odyssey")).not.toBeInTheDocument();
  });

  it("shows a kind-aware empty state", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      { id: "2", title: "A Blog Post", status: "SUMMARISED", kind: "ARTICLE" },
    ]);

    renderWithClient(<App />, "/");

    // Only an article exists, so the default Books grid is empty.
    expect(await screen.findByText("No books yet.")).toBeInTheDocument();
  });
});
