import type { ComponentType, SVGProps } from "react";
import {
  BrightnessLowIcon,
  PersonOffIcon,
  VideoOffIcon,
} from "@/components/icons";

/**
 * MOCK data for the static M2 build. The live upload → analyze loop lands in
 * M3, and the real flaw catalog / validation in M5–M6. These shapes mirror the
 * PRD: top 2–3 flaws, each with one fix tip (text only); rejection screen shows
 * specific reasons.
 */

export type Flaw = {
  priority: number;
  category: string;
  title: string;
  description: string;
  fix: string;
};

export type RejectionReason = {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
  title: string;
};

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
  { icon: VideoOffIcon, label: "Reason 01", title: "Angle too wide" },
  { icon: BrightnessLowIcon, label: "Reason 02", title: "Low lighting" },
  { icon: PersonOffIcon, label: "Reason 03", title: "No golfer detected" },
];
