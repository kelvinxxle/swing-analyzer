import type { ComponentType, SVGProps } from "react";
import {
  BrightnessLowIcon,
  PersonOffIcon,
  VideoOffIcon,
} from "@/components/icons";

/**
 * Shared types + helpers for the `/analyze` loop (M3). These mirror the FastAPI
 * contract (`backend/app/analysis.py`) so the live JSON renders on the existing
 * results / error screens with minimal change.
 */

export type AnalysisStatus = "analyzed" | "no_major_flaws" | "rejected";

export type Flaw = {
  priority: number;
  category: string;
  title: string;
  description: string;
  fix: string;
};

/** A rejection icon code; resolved to a component via {@link REASON_ICONS}. */
export type ReasonCode = "angle" | "lighting" | "no_golfer";

export type RejectionReason = {
  code: ReasonCode;
  label: string;
  title: string;
};

export type Rejection = {
  headline: string;
  summary: string;
  details: RejectionReason[];
};

export type AnalyzeResponse = {
  status: AnalysisStatus;
  flaws: Flaw[];
  reason?: Rejection | null;
};

/** Maps a serializable reason `code` to its icon (icons can't cross JSON). */
export const REASON_ICONS: Record<
  ReasonCode,
  ComponentType<SVGProps<SVGSVGElement>>
> = {
  angle: VideoOffIcon,
  lighting: BrightnessLowIcon,
  no_golfer: PersonOffIcon,
};

/** Where a given status routes in the one-shot flow. */
export function destinationFor(status: AnalysisStatus): "/results" | "/error" {
  return status === "rejected" ? "/error" : "/results";
}

/**
 * Ephemeral, browser-only handoff between the upload screen and the result
 * screens. Consistent with the PRD's no-persistence rule — nothing is stored
 * server-side and the value lives only for the tab session.
 */
export const ANALYSIS_STORAGE_KEY = "swing-analysis-result";

export function storeAnalysis(result: AnalyzeResponse): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(result));
}

export function readAnalysis(): AnalyzeResponse | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ANALYSIS_STORAGE_KEY);
  if (!raw) return null;
  try {
    return parseAnalyzeResponse(JSON.parse(raw));
  } catch {
    return null;
  }
}

/** Narrowing parse so malformed payloads fail closed instead of rendering junk. */
export function parseAnalyzeResponse(value: unknown): AnalyzeResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("Invalid analyze response: not an object");
  }
  const record = value as Record<string, unknown>;
  const status = record.status;
  if (
    status !== "analyzed" &&
    status !== "no_major_flaws" &&
    status !== "rejected"
  ) {
    throw new Error(`Invalid analyze response: unknown status ${String(status)}`);
  }
  const flaws = Array.isArray(record.flaws) ? (record.flaws as Flaw[]) : [];
  const reason =
    record.reason && typeof record.reason === "object"
      ? (record.reason as Rejection)
      : null;
  return { status, flaws, reason };
}
