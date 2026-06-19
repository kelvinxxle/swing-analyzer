type ProgressBarProps = {
  /** 0–100 for a determinate bar. Omit for an indeterminate animated bar. */
  value?: number;
  label?: string;
  className?: string;
};

/**
 * Linear, high-contrast progress indicator (electric-green fill on a dark
 * track), per the Apex Mechanics design system: "Avoid circular spinners to
 * maintain the linear, data-driven feel."
 */
export function ProgressBar({ value, label, className }: ProgressBarProps) {
  const indeterminate = value === undefined;
  const clamped = indeterminate
    ? undefined
    : Math.max(0, Math.min(100, value));

  return (
    <div className={className}>
      {label ? (
        <div className="mb-2 flex items-center justify-between font-mono text-data-label uppercase text-on-surface-secondary">
          <span>{label}</span>
          {!indeterminate ? <span>{clamped}%</span> : null}
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-label={label ?? "Progress"}
        aria-valuemin={indeterminate ? undefined : 0}
        aria-valuemax={indeterminate ? undefined : 100}
        aria-valuenow={clamped}
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface-variant"
      >
        {indeterminate ? (
          <div className="h-full w-1/3 animate-progress-indeterminate rounded-full bg-accent-electric" />
        ) : (
          <div
            className="h-full rounded-full bg-accent-electric transition-[width] duration-200 ease-out"
            style={{ width: `${clamped}%` }}
          />
        )}
      </div>
    </div>
  );
}
