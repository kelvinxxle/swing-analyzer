import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReasonCard } from "@/components/ReasonCard";

describe("ReasonCard", () => {
  it("renders the label, title and an icon resolved from the code", () => {
    const { container } = render(
      <ReasonCard
        reason={{ code: "no_golfer", label: "Reason 03", title: "No golfer detected" }}
      />,
    );
    expect(screen.getByText(/reason 03/i)).toBeInTheDocument();
    expect(screen.getByText(/no golfer detected/i)).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("resolves an icon for a new M5 reason code", () => {
    const { container } = render(
      <ReasonCard
        reason={{ code: "too_short", label: "Reason 01", title: "Clip too short" }}
      />,
    );
    expect(screen.getByText(/clip too short/i)).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
  });
});
