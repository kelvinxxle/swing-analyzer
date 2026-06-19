export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-container flex-col items-center justify-center px-margin-mobile py-16 text-center md:px-margin-desktop">
      <p className="font-mono text-data-label uppercase text-accent-electric">
        Swing Analyzer · v1
      </p>

      <h1 className="mt-4 font-display text-headline-lg-mobile text-on-surface-primary md:text-headline-xl">
        Upload one swing.
        <br />
        Get your top flaws.
      </h1>

      <p className="mt-6 max-w-md font-sans text-body-md text-on-surface-secondary">
        Precise, prioritized fixes for intermediate amateurs — fast. This is the
        M1 foundation placeholder; the full experience ships across later
        milestones.
      </p>

      <div className="mt-10 w-full max-w-sm rounded-lg border border-dashed border-on-surface-secondary bg-surface-elevated p-gutter">
        <span className="font-mono text-data-label uppercase text-on-surface-secondary">
          Status
        </span>
        <p className="mt-2 font-sans text-body-sm text-on-surface-primary">
          Foundation &amp; deploy pipeline online.
        </p>
      </div>

      <button
        type="button"
        className="mt-10 w-full max-w-sm rounded bg-accent-electric px-6 py-3 font-display text-button-text uppercase text-surface-base transition hover:brightness-110"
      >
        Coming soon
      </button>
    </main>
  );
}
