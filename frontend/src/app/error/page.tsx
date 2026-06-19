import { CtaButton } from "@/components/CtaButton";
import { ReasonCard } from "@/components/ReasonCard";
import { ErrorCircleIcon, ReplayIcon } from "@/components/icons";
import { MOCK_REJECTION_REASONS } from "@/lib/mock-data";

export default function ErrorPage() {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      <div aria-hidden className="pointer-events-none fixed inset-0 grid-bg" />

      <div className="fixed top-0 z-50 w-full bg-status-error px-4 py-2 text-center font-mono text-data-label uppercase tracking-widest text-white shadow-md">
        System Alert: Invalid Video Input Detected
      </div>

      <main className="relative z-10 mx-auto flex w-full max-w-container flex-1 flex-col items-center justify-center px-margin-mobile pb-16 pt-20 md:px-margin-desktop">
        <div className="relative w-full overflow-hidden rounded-xl border border-status-error/30 bg-surface-elevated p-8 text-center shadow-lg">
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-12 h-32 w-32 -translate-x-1/2 rounded-full bg-status-error/10 blur-2xl"
          />

          <ErrorCircleIcon className="mx-auto mb-6 h-16 w-16 text-status-error" />

          <h1 className="font-display text-headline-xl uppercase tracking-tight text-status-error">
            Analysis Failed
          </h1>

          <p className="mx-auto mt-3 max-w-md font-sans text-body-md text-on-surface-secondary">
            The video provided does not meet the guidelines required for
            auto-detection. Our system cannot accurately diagnose your swing.
          </p>

          <div className="mt-8 grid grid-cols-1 gap-4 text-left md:grid-cols-3">
            {MOCK_REJECTION_REASONS.map((reason) => (
              <ReasonCard key={reason.label} reason={reason} />
            ))}
          </div>

          <div className="mt-10">
            <CtaButton href="/upload" className="md:mx-auto md:w-auto md:px-12">
              <ReplayIcon className="h-5 w-5" />
              Try Again
            </CtaButton>
          </div>

          <p className="mt-6 font-mono text-data-label uppercase tracking-widest text-on-surface-secondary opacity-60">
            Review guidelines before re-uploading
          </p>
        </div>
      </main>
    </div>
  );
}
