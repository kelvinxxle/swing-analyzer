import type { Flaw, RejectionReason } from "@/lib/analysis";

export type { Flaw, RejectionReason } from "@/lib/analysis";

/**
 * Sample data mirroring the live `/analyze` contract. Used as a graceful
 * fallback when a result screen is opened directly (no upload in this tab) and
 * as fixtures for tests. The real flaw catalog / validation land in M5–M6.
 */

export const MOCK_FLAWS: Flaw[] = [
  {
    priority: 1,
    category: "Posture Loss",
    title: "Early Extension",
    description:
      "Your hips move closer to the ball during the downswing, forcing you to stand up and lose your posture, which leads to inconsistent contact and loss of power.",
    fix: "Keep your glutes against an imaginary wall during the downswing. Feel your left hip push back and clear, rather than thrusting forward toward the ball.",
  },
  {
    priority: 2,
    category: "Path",
    title: "Over the Top",
    description:
      "Your downswing starts with the upper body and shoulders spinning out, causing the club path to travel outside-in relative to the target line, resulting in pulls or weak slices.",
    fix: "Initiate the downswing from the ground up. Allow your arms to 'drop' into the slot naturally before your shoulders begin to aggressively rotate toward the target.",
  },
];

export const MOCK_REJECTION_REASONS: RejectionReason[] = [
  { code: "angle", label: "Reason 01", title: "Angle too wide" },
  { code: "lighting", label: "Reason 02", title: "Low lighting" },
  { code: "no_golfer", label: "Reason 03", title: "No golfer detected" },
];
