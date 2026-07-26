import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import * as api from "../api/documents";
import { renderWithClient } from "../test-utils";

// Mock only the network calls; keep isPending (the polling predicate) real.
vi.mock("../api/documents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/documents")>();
  return {
    ...actual,
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    getSummary: vi.fn(),
    getContent: vi.fn(),
  };
});

const mockedApi = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminPage", () => {
  it("renders documents and their status from the read side", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED" },
      { id: "2", title: "Draft notes", status: "EXTRACTING" },
    ]);

    renderWithClient(<App />, "/admin");

    expect(await screen.findByText("The Odyssey")).toBeInTheDocument();
    expect(screen.getByText("Summarised")).toBeInTheDocument();
    expect(screen.getByText("Extracting")).toBeInTheDocument();
  });

  it("shows an empty state when there are no documents", async () => {
    mockedApi.listDocuments.mockResolvedValue([]);

    renderWithClient(<App />, "/admin");

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });

  it("uploads a document with its title and file", async () => {
    const user = userEvent.setup();
    mockedApi.listDocuments.mockResolvedValue([]);
    mockedApi.uploadDocument.mockResolvedValue({
      id: "3",
      title: "New paper",
      status: "UPLOADED",
    });

    renderWithClient(<App />, "/admin");
    await screen.findByText(/no documents yet/i);

    await user.type(screen.getByLabelText("Title"), "New paper");
    const file = new File(["%PDF-1.4"], "paper.pdf", {
      type: "application/pdf",
    });
    await user.upload(screen.getByLabelText("PDF"), file);
    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() =>
      expect(mockedApi.uploadDocument).toHaveBeenCalledWith("New paper", file),
    );
  });

  it("deletes a document", async () => {
    const user = userEvent.setup();
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED" },
    ]);
    mockedApi.deleteDocument.mockResolvedValue(undefined);

    renderWithClient(<App />, "/admin");
    await screen.findByText("The Odyssey");

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(mockedApi.deleteDocument).toHaveBeenCalledWith("1"),
    );
  });

  it("opens a summary for a summarised document", async () => {
    const user = userEvent.setup();
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED" },
    ]);
    mockedApi.getSummary.mockResolvedValue({ text: "A hero sails home." });

    renderWithClient(<App />, "/admin");
    await screen.findByText("The Odyssey");

    await user.click(screen.getByRole("button", { name: "View summary" }));

    expect(await screen.findByText("A hero sails home.")).toBeInTheDocument();
    expect(mockedApi.getSummary).toHaveBeenCalledWith("1");
  });

  it("opens the extracted text for an extracted document", async () => {
    const user = userEvent.setup();
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "EXTRACTED" },
    ]);
    mockedApi.getContent.mockResolvedValue("## Book I\n\nSing to me of the man…");

    renderWithClient(<App />, "/admin");
    await screen.findByText("The Odyssey");

    await user.click(screen.getByRole("button", { name: "View extracted" }));

    expect(
      await screen.findByRole("heading", { name: "Book I" }),
    ).toBeInTheDocument();
    expect(mockedApi.getContent).toHaveBeenCalledWith("1");
  });

  it("links to the original PDF for every document", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "Draft notes", status: "UPLOADED" },
    ]);

    renderWithClient(<App />, "/admin");
    await screen.findByText("Draft notes");

    expect(screen.getByRole("link", { name: "View PDF" })).toHaveAttribute(
      "href",
      "/api/documents/1/file",
    );
  });

  it("renders the summary Markdown as formatted elements, not raw text", async () => {
    const user = userEvent.setup();
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED" },
    ]);
    mockedApi.getSummary.mockResolvedValue({
      text: "## Themes\n\n- **Homecoming** and cunning.",
    });

    renderWithClient(<App />, "/admin");
    await screen.findByText("The Odyssey");
    await user.click(screen.getByRole("button", { name: "View summary" }));

    expect(
      await screen.findByRole("heading", { name: "Themes" }),
    ).toBeInTheDocument();
    // The bold marker is rendered, not shown literally.
    expect(screen.getByText("Homecoming").tagName).toBe("STRONG");
    expect(screen.queryByText(/\*\*Homecoming\*\*/)).not.toBeInTheDocument();
  });
});
