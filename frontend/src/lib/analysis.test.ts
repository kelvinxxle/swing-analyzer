import { afterEach, describe, expect, it } from "vitest";
import {
  ANALYSIS_STORAGE_KEY,
  analyzeEndpoint,
  destinationFor,
  parseAnalyzeResponse,
  readAnalysis,
  storeAnalysis,
  type AnalyzeResponse,
} from "@/lib/analysis";

afterEach(() => {
  window.sessionStorage.clear();
});

describe("destinationFor", () => {
  it("routes rejected to the error screen", () => {
    expect(destinationFor("rejected")).toBe("/error");
  });

  it("routes analyzed and no_major_flaws to the results screen", () => {
    expect(destinationFor("analyzed")).toBe("/results");
    expect(destinationFor("no_major_flaws")).toBe("/results");
  });
});

describe("parseAnalyzeResponse", () => {
  it("accepts a valid analyzed response", () => {
    const parsed = parseAnalyzeResponse({
      status: "analyzed",
      flaws: [
        {
          priority: 1,
          category: "Path",
          title: "Over the Top",
          description: "d",
          fix: "f",
        },
      ],
    });
    expect(parsed.status).toBe("analyzed");
    expect(parsed.flaws).toHaveLength(1);
  });

  it("rejects an unknown status", () => {
    expect(() => parseAnalyzeResponse({ status: "weird", flaws: [] })).toThrow();
  });

  it("rejects non-objects", () => {
    expect(() => parseAnalyzeResponse(null)).toThrow();
  });

  it("rejects when flaws is not an array", () => {
    expect(() =>
      parseAnalyzeResponse({ status: "analyzed", flaws: "nope" }),
    ).toThrow();
  });

  it("rejects a malformed flaw (missing fix)", () => {
    expect(() =>
      parseAnalyzeResponse({
        status: "analyzed",
        flaws: [{ priority: 1, category: "Path", title: "t", description: "d" }],
      }),
    ).toThrow();
  });

  it("accepts a valid rejected response", () => {
    const parsed = parseAnalyzeResponse({
      status: "rejected",
      flaws: [],
      reason: {
        headline: "Invalid Video Input Detected",
        summary: "nope",
        details: [{ code: "angle", label: "Reason 01", title: "Angle too wide" }],
      },
    });
    expect(parsed.status).toBe("rejected");
    expect(parsed.reason?.details).toHaveLength(1);
  });

  it("rejects a reason detail with an unknown code", () => {
    expect(() =>
      parseAnalyzeResponse({
        status: "rejected",
        flaws: [],
        reason: {
          headline: "h",
          summary: "s",
          details: [{ code: "lava", label: "Reason 01", title: "t" }],
        },
      }),
    ).toThrow();
  });

  it("rejects a reason missing summary", () => {
    expect(() =>
      parseAnalyzeResponse({
        status: "rejected",
        flaws: [],
        reason: { headline: "h", details: [] },
      }),
    ).toThrow();
  });
});

describe("analyzeEndpoint", () => {
  it("targets the backend /analyze path", () => {
    expect(analyzeEndpoint()).toMatch(/\/analyze$/);
  });
});

describe("session storage handoff", () => {
  it("stores and reads a result", () => {
    const result: AnalyzeResponse = {
      status: "no_major_flaws",
      flaws: [],
      reason: null,
    };
    storeAnalysis(result);
    expect(window.sessionStorage.getItem(ANALYSIS_STORAGE_KEY)).not.toBeNull();
    expect(readAnalysis()).toEqual(result);
  });

  it("returns null when nothing is stored", () => {
    expect(readAnalysis()).toBeNull();
  });

  it("returns null for corrupt storage", () => {
    window.sessionStorage.setItem(ANALYSIS_STORAGE_KEY, "not json");
    expect(readAnalysis()).toBeNull();
  });
});
