import { AppHeader } from "@/components/AppHeader";
import { BottomNav } from "@/components/BottomNav";
import { CtaButton } from "@/components/CtaButton";
import { FlawCard } from "@/components/FlawCard";
import { MOCK_FLAWS } from "@/lib/mock-data";

export default function ResultsPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader variant="centered" />

      <main className="mx-auto w-full max-w-container flex-1 px-margin-mobile py-8 md:px-margin-desktop">
        <h1 className="font-display text-headline-xl uppercase text-on-surface-primary">
          Swing Report
        </h1>
        <p className="mt-2 font-sans text-body-md text-on-surface-secondary">
          Analysis complete. Top priority fixes identified.
        </p>

        <div className="mt-8 space-y-6">
          {MOCK_FLAWS.map((flaw) => (
            <FlawCard key={flaw.priority} flaw={flaw} />
          ))}
        </div>

        <div className="mt-8">
          <CtaButton href="/upload">Upload Next Swing</CtaButton>
        </div>
      </main>

      <BottomNav active="sessions" />
    </div>
  );
}
