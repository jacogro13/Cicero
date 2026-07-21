import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

// Smoke test: the shell renders and CSS Modules resolve to a class name — proof
// the Vite + Vitest + Testing Library + CSS Modules toolchain is wired (ADR-017).
describe("App", () => {
  it("renders the admin shell", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Cicero" })).toBeInTheDocument();
  });
});
