import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MarkdownModal } from "./MarkdownModal";

const baseProps = {
  ariaLabel: "Extracted text",
  title: "Clean Code",
  isLoading: false,
  isError: false,
  loadingLabel: "Loading…",
  errorLabel: "Could not load.",
  markdown: "# Heading\n\nBody.",
};

describe("MarkdownModal", () => {
  it("closes on Escape, without needing to scroll back to the button", () => {
    const onClose = vi.fn();
    render(<MarkdownModal {...baseProps} onClose={onClose} />);

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when the × button is clicked", () => {
    const onClose = vi.fn();
    render(<MarkdownModal {...baseProps} onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
