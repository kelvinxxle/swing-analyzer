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
 * Absolute URL of the FastAPI `/analyze` endpoint. The browser posts the video
 * straight to the backend (not through a Next.js proxy): a Vercel serverless
 * function would buffer the body and reject uploads over ~4.5MB, while the UI
 * allows up to 50MB. `NEXT_PUBLIC_API_URL` is public by design; CORS on the
 * backend already allows the Vercel origin.
 */
export function analyzeEndpoint(): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return `${base.replace(/\/$/, "")}/analyze`;
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

const REASON_CODES: ReasonCode[] = ["angle", "lighting", "no_golfer"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseFlaw(value: unknown): Flaw {
  if (!isRecord(value)) {
    throw new Error("Invalid analyze response: flaw is not an object");
  }
  const { priority, category, title, description, fix } = value;
  if (
    typeof priority !== "number" ||
    typeof category !== "string" ||
    typeof title !== "string" ||
    typeof description !== "string" ||
    typeof fix !== "string"
  ) {
    throw new Error("Invalid analyze response: malformed flaw");
  }
  return { priority, category, title, description, fix };
}

function parseRejectionDetail(value: unknown): RejectionReason {
  if (!isRecord(value)) {
    throw new Error("Invalid analyze response: reason detail is not an object");
  }
  const { code, label, title } = value;
  if (
    typeof code !== "string" ||
    !REASON_CODES.includes(code as ReasonCode) ||
    typeof label !== "string" ||
    typeof title !== "string"
  ) {
    throw new Error("Invalid analyze response: malformed reason detail");
  }
  return { code: code as ReasonCode, label, title };
}

function parseRejection(value: unknown): Rejection {
  if (!isRecord(value)) {
    throw new Error("Invalid analyze response: reason is not an object");
  }
  const { headline, summary, details } = value;
  if (typeof headline !== "string" || typeof summary !== "string") {
    throw new Error("Invalid analyze response: malformed reason");
  }
  if (!Array.isArray(details)) {
    throw new Error("Invalid analyze response: reason.details is not an array");
  }
  return { headline, summary, details: details.map(parseRejectionDetail) };
}

/**
 * Narrowing parse so malformed payloads fail closed instead of rendering junk.
 * Every field is validated — including each flaw's shape and each rejection
 * detail's `code` — so `readAnalysis()` returns null (rather than crashing
 * `REASON_ICONS[code]`) on anything unexpected.
 */
export function parseAnalyzeResponse(value: unknown): AnalyzeResponse {
  if (!isRecord(value)) {
    throw new Error("Invalid analyze response: not an object");
  }
  const status = value.status;
  if (
    status !== "analyzed" &&
    status !== "no_major_flaws" &&
    status !== "rejected"
  ) {
    throw new Error(`Invalid analyze response: unknown status ${String(status)}`);
  }

  if (!Array.isArray(value.flaws)) {
    throw new Error("Invalid analyze response: flaws is not an array");
  }
  const flaws = value.flaws.map(parseFlaw);

  const reason =
    value.reason === undefined || value.reason === null
      ? null
      : parseRejection(value.reason);

  return { status, flaws, reason };
}
