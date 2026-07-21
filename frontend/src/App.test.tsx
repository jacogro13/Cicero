import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import * as api from "./api/documents";
import { renderWithClient } from "./test-utils";

// Mock only the network calls; keep isPending (the polling predicate) real.
vi.mock("./api/documents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/documents")>();
  return {
    ...actual,
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    getSummary: vi.fn(),
  };
});

const mockedApi = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("App", () => {
  it("renders documents and their status from the read side", async () => {
    mockedApi.listDocuments.mockResolvedValue([
      { id: "1", title: "The Odyssey", status: "SUMMARISED" },
      { id: "2", title: "Draft notes", status: "EXTRACTING" },
    ]);

    renderWithClient(<App />);

    expect(await screen.findByText("The Odyssey")).toBeInTheDocument();
    expect(screen.getByText("Summarised")).toBeInTheDocument();
    expect(screen.getByText("Extracting")).toBeInTheDocument();
  });

  it("shows an empty state when there are no documents", async () => {
    mockedApi.listDocuments.mockResolvedValue([]);

    renderWithClient(<App />);

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

    renderWithClient(<App />);
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

    renderWithClient(<App />);
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

    renderWithClient(<App />);
    await screen.findByText("The Odyssey");

    await user.click(screen.getByRole("button", { name: "View summary" }));

    expect(await screen.findByText("A hero sails home.")).toBeInTheDocument();
    expect(mockedApi.getSummary).toHaveBeenCalledWith("1");
  });
});
