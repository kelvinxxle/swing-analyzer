import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ResultsPage from "./page";
import { ANALYSIS_STORAGE_KEY, type AnalyzeResponse } from "@/lib/analysis";

function seed(result: AnalyzeResponse) {
  window.sessionStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(result));
}

afterEach(() => {
  window.sessionStorage.clear();
});

describe("Results screen", () => {
  it("renders prioritized flaw cards for an analyzed result", async () => {
    seed({
      status: "analyzed",
      flaws: [
        {
          priority: 1,
          category: "Posture Loss",
          title: "Early Extension",
          description: "Your hips push toward the ball.",
          fix: "Keep your glutes back.",
        },
        {
          priority: 2,
          category: "Path",
          title: "Over the Top",
          description: "Hands move out from the top.",
          fix: "Drop into the slot.",
        },
      ],
      reason: null,
    });

    render(<ResultsPage />);

    expect(
      await screen.findByRole("heading", { name: /early extension/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /over the top/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/keep your glutes back/i)).toBeInTheDocument();
  });

  it("renders the positive state for no_major_flaws", async () => {
    seed({ status: "no_major_flaws", flaws: [], reason: null });

    render(<ResultsPage />);

    expect(
      await screen.findByRole("heading", { name: /no major flaws detected/i }),
    ).toBeInTheDocument();
  });

  it("shows the empty state when nothing has been analyzed", async () => {
    render(<ResultsPage />);

    expect(
      await screen.findByRole("heading", { name: /no analysis yet/i }),
    ).toBeInTheDocument();
  });
});
