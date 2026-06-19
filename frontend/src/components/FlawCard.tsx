import { WarningTriangleIcon, WrenchIcon } from "@/components/icons";
import type { Flaw } from "@/lib/mock-data";

/**
 * Analysis result card. A vertical status bar on the left edge (status-warning
 * for a detected flaw) allows quick scanning, per the design system.
 */
export function FlawCard({ flaw }: { flaw: Flaw }) {
  return (
    <article className="relative overflow-hidden rounded-lg border border-surface-variant/60 bg-surface-elevated p-gutter pl-6">
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-1.5 bg-status-warning"
      />

      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-data-label uppercase text-status-warning">
          Priority {flaw.priority} &middot; {flaw.category}
        </p>
        <WarningTriangleIcon className="h-5 w-5 shrink-0 text-status-warning" />
      </div>

      <h2 className="mt-2 font-display text-headline-lg-mobile text-on-surface-primary">
        {flaw.title}
      </h2>

      <p className="mt-3 font-sans text-body-md text-on-surface-secondary">
        {flaw.description}
      </p>

      <div className="mt-5 rounded-md border border-surface-variant/60 bg-surface-overlay p-4">
        <p className="flex items-center gap-2 font-mono text-data-label uppercase text-accent-electric">
          <WrenchIcon className="h-4 w-4" />
          The Fix
        </p>
        <p className="mt-2 font-sans text-body-md text-on-surface-primary">
          {flaw.fix}
        </p>
      </div>
    </article>
  );
}
