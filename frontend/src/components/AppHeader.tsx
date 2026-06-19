import Link from "next/link";
import { MenuIcon, UserCircleIcon } from "@/components/icons";

type AppHeaderProps = {
  /**
   * "full" shows the menu + profile controls (Upload screen).
   * "centered" shows just the centered wordmark (Results screen).
   */
  variant?: "full" | "centered";
};

/**
 * Top app bar with the "SWING ANALYTICS" wordmark in electric green.
 */
export function AppHeader({ variant = "full" }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-surface-variant/60 bg-surface-base/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-container items-center justify-between px-margin-mobile md:px-margin-desktop">
        {variant === "full" ? (
          <button
            type="button"
            aria-label="Open menu"
            className="text-accent-electric"
          >
            <MenuIcon />
          </button>
        ) : (
          <span className="w-6" aria-hidden />
        )}

        <Link
          href="/upload"
          className="font-display text-data-label font-bold uppercase tracking-[0.2em] text-accent-electric md:text-base"
        >
          Swing Analytics
        </Link>

        {variant === "full" ? (
          <button
            type="button"
            aria-label="Profile"
            className="text-accent-electric"
          >
            <UserCircleIcon />
          </button>
        ) : (
          <span className="w-6" aria-hidden />
        )}
      </div>
    </header>
  );
}
