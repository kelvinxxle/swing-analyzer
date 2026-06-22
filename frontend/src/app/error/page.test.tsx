import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorPage from "./page";
import { ANALYSIS_STORAGE_KEY, type AnalyzeResponse } from "@/lib/analysis";

function seed(result: AnalyzeResponse) {
  window.sessionStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(result));
}

afterEach(() => {
  window.sessionStorage.clear();
});

describe("Error screen", () => {
  it("renders the specific rejection reason", async () => {
    seed({
      status: "rejected",
      flaws: [],
      reason: {
        headline: "Invalid Video Input Detected",
        summary: "The clip is too dark to analyze.",
        details: [{ code: "lighting", label: "Reason 01", title: "Low lighting" }],
      },
    });

    render(<ErrorPage />);

    expect(
      screen.getByRole("heading", { name: /analysis failed/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/the clip is too dark/i)).toBeInTheDocument();
    expect(screen.getByText(/low lighting/i)).toBeInTheDocument();
  });

  it("falls back to a generic message when no reason is stored", () => {
    render(<ErrorPage />);

    expect(
      screen.getByRole("heading", { name: /analysis failed/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/does not meet the guidelines/i)).toBeInTheDocument();
  });
});
