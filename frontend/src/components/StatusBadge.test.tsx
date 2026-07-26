import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("shows a document waiting to be extracted as queued for that stage", () => {
    render(<StatusBadge status="UPLOADED" />);

    // A document waiting behind a busy worker reads as "Queued", not a mystery stall,
    // and the qualifier names the stage it is waiting for.
    const badge = screen.getByText("Queued · extract");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", expect.stringMatching(/extract/i));
  });

  it("shows a document waiting to be summarised as queued for that stage", () => {
    render(<StatusBadge status="EXTRACTED" />);

    const badge = screen.getByText("Queued · summary");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", expect.stringMatching(/summaris/i));
  });

  it("keeps the active-stage labels", () => {
    render(<StatusBadge status="SUMMARISING" />);
    expect(screen.getByText("Summarising")).toBeInTheDocument();
  });
});
