import { REASON_ICONS, type RejectionReason } from "@/lib/analysis";

/**
 * A single rejection reason on the error screen: a warning-colored icon, a
 * monospaced "REASON 0N" label, and the specific reason text. The icon is
 * resolved from the serializable `code` returned by the API.
 */
export function ReasonCard({ reason }: { reason: RejectionReason }) {
  const Icon = REASON_ICONS[reason.code];
  return (
    <div className="flex flex-col items-start rounded-lg border border-surface-variant bg-surface-overlay p-4 text-left">
      <Icon className="mb-3 h-6 w-6 text-status-warning" />
      <span className="font-mono text-data-label uppercase text-on-surface-secondary">
        {reason.label}
      </span>
      <span className="mt-1 font-sans text-body-md font-semibold text-on-surface-primary">
        {reason.title}
      </span>
    </div>
  );
}
