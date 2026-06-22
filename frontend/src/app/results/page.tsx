"use client";

import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { BottomNav } from "@/components/BottomNav";
import { CtaButton } from "@/components/CtaButton";
import { FlawCard } from "@/components/FlawCard";
import { ScanFrameIcon } from "@/components/icons";
import { readAnalysis, type AnalyzeResponse } from "@/lib/analysis";

export default function ResultsPage() {
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setResult(readAnalysis());
    setReady(true);
  }, []);

  const hasFlaws = (result?.flaws.length ?? 0) > 0;

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader variant="centered" />

      <main className="mx-auto w-full max-w-container flex-1 px-margin-mobile py-8 md:px-margin-desktop">
        <h1 className="font-display text-headline-xl uppercase text-on-surface-primary">
          Swing Report
        </h1>
        <p className="mt-2 font-sans text-body-md text-on-surface-secondary">
          {hasFlaws
            ? "Analysis complete. Top priority fixes identified."
            : "Analysis complete."}
        </p>

        {!ready ? null : !result ? (
          <NoResult />
        ) : hasFlaws ? (
          <>
            <div className="mt-8 space-y-6">
              {result.flaws.map((flaw) => (
                <FlawCard key={flaw.priority} flaw={flaw} />
              ))}
            </div>
            <div className="mt-8">
              <CtaButton href="/upload">Upload Next Swing</CtaButton>
            </div>
          </>
        ) : (
          <NoMajorFlaws />
        )}
      </main>

      <BottomNav active="sessions" />
    </div>
  );
}

function NoMajorFlaws() {
  return (
    <div className="mt-8">
      <div className="rounded-lg border border-accent-electric/40 bg-surface-elevated p-gutter text-center">
        <ScanFrameIcon className="mx-auto h-12 w-12 text-accent-electric" />
        <h2 className="mt-4 font-display text-headline-lg-mobile text-on-surface-primary">
          No Major Flaws Detected
        </h2>
        <p className="mx-auto mt-3 max-w-md font-sans text-body-md text-on-surface-secondary">
          We scanned your swing against the catalog and didn&apos;t find a major
          fault from this angle. Keep grooving it — upload another swing anytime.
        </p>
      </div>
      <div className="mt-8">
        <CtaButton href="/upload">Upload Next Swing</CtaButton>
      </div>
    </div>
  );
}

function NoResult() {
  return (
    <div className="mt-8">
      <div className="rounded-lg border border-surface-variant/60 bg-surface-elevated p-gutter text-center">
        <h2 className="font-display text-headline-lg-mobile text-on-surface-primary">
          No Analysis Yet
        </h2>
        <p className="mx-auto mt-3 max-w-md font-sans text-body-md text-on-surface-secondary">
          Upload a swing to see your prioritized fixes here.
        </p>
      </div>
      <div className="mt-8">
        <CtaButton href="/upload">Upload a Swing</CtaButton>
      </div>
    </div>
  );
}
