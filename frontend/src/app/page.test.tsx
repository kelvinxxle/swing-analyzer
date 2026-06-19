import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import WelcomePage from "./page";

describe("Welcome page", () => {
  it("renders the product headline", () => {
    render(<WelcomePage />);
    expect(
      screen.getByRole("heading", { name: /master your swing/i }),
    ).toBeInTheDocument();
  });

  it("links the primary CTA to the upload screen", () => {
    render(<WelcomePage />);
    const cta = screen.getByRole("link", { name: /let's analyze/i });
    expect(cta).toHaveAttribute("href", "/upload");
  });

  it("lists the three capture guidelines", () => {
    render(<WelcomePage />);
    expect(
      screen.getByRole("heading", { name: /record down-the-line/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /ensure good lighting/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /keep full swing in frame/i }),
    ).toBeInTheDocument();
  });
});
