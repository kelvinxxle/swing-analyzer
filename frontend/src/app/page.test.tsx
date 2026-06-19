import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "./page";

describe("Home page", () => {
  it("renders the product headline", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { name: /get your top flaws/i }),
    ).toBeInTheDocument();
  });

  it("shows the foundation status", () => {
    render(<Home />);
    expect(
      screen.getByText(/foundation & deploy pipeline online/i),
    ).toBeInTheDocument();
  });
});
