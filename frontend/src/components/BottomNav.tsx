import Link from "next/link";
import type { ComponentType, SVGProps } from "react";
import {
  DashboardIcon,
  HistoryIcon,
  PlusCircleIcon,
  UserIcon,
} from "@/components/icons";

type TabKey = "dashboard" | "upload" | "sessions" | "profile";

type Tab = {
  key: TabKey;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  href?: string;
};

/**
 * Bottom tab bar. Only "Upload" is functional in v1 — Dashboard / Sessions /
 * Profile imply accounts & history, which the PRD explicitly excludes. They are
 * rendered as disabled chrome to stay faithful to the mockups.
 */
const TABS: Tab[] = [
  { key: "dashboard", label: "Dashboard", icon: DashboardIcon },
  { key: "upload", label: "Upload", icon: PlusCircleIcon, href: "/upload" },
  { key: "sessions", label: "Sessions", icon: HistoryIcon },
  { key: "profile", label: "Profile", icon: UserIcon },
];

type BottomNavProps = {
  active: TabKey;
};

export function BottomNav({ active }: BottomNavProps) {
  return (
    <nav
      aria-label="Primary"
      className="sticky bottom-0 z-30 border-t border-surface-variant/60 bg-surface-base/95 backdrop-blur"
    >
      <ul className="mx-auto flex max-w-container items-stretch justify-around px-2 py-2">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = tab.key === active;
          const interactive = Boolean(tab.href);

          const content = (
            <span
              className={`flex flex-col items-center gap-1 rounded-md px-3 py-1.5 ${
                isActive
                  ? "bg-surface-overlay text-accent-electric"
                  : "text-on-surface-secondary"
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="font-mono text-[10px] uppercase tracking-wider">
                {tab.label}
              </span>
            </span>
          );

          return (
            <li key={tab.key} className="flex-1">
              {interactive ? (
                <Link
                  href={tab.href as string}
                  aria-current={isActive ? "page" : undefined}
                  className="flex justify-center"
                >
                  {content}
                </Link>
              ) : (
                <span
                  aria-disabled="true"
                  className="flex cursor-not-allowed justify-center opacity-60"
                >
                  {content}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
