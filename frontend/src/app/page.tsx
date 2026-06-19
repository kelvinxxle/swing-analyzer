import { CtaButton } from "@/components/CtaButton";
import { GuidelineItem } from "@/components/GuidelineItem";
import {
  ArrowRightIcon,
  LightbulbIcon,
  ScanFrameIcon,
  VideoIcon,
} from "@/components/icons";

const GUIDELINES = [
  {
    icon: VideoIcon,
    title: "Record Down-the-Line",
    description:
      "Position the camera directly behind the hands, facing the target.",
  },
  {
    icon: LightbulbIcon,
    title: "Ensure Good Lighting",
    description:
      "Avoid heavy shadows. Bright, even lighting provides the best results.",
  },
  {
    icon: ScanFrameIcon,
    title: "Keep Full Swing in Frame",
    description:
      "The clubhead and body must remain visible from setup to finish.",
  },
];

export default function WelcomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-container flex-col px-margin-mobile pb-8 pt-16 md:px-margin-desktop">
      <div className="flex flex-1 flex-col">
        <h1 className="text-center font-display text-headline-xl text-on-surface-primary">
          Master Your Swing
        </h1>
        <p className="mt-4 text-center font-sans text-body-md text-on-surface-secondary">
          One swing. One angle. Fast diagnosis.
        </p>

        <section className="mt-10 divide-y divide-surface-variant/60 rounded-lg border border-surface-variant/60 bg-surface-elevated px-gutter">
          {GUIDELINES.map((g) => (
            <GuidelineItem
              key={g.title}
              icon={g.icon}
              title={g.title}
              description={g.description}
            />
          ))}
        </section>
      </div>

      <div className="mt-10">
        <CtaButton href="/upload">
          Got it, Let&apos;s Analyze
          <ArrowRightIcon className="h-5 w-5" />
        </CtaButton>
      </div>
    </main>
  );
}
