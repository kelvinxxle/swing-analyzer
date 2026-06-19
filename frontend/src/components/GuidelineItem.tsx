import type { ComponentType, SVGProps } from "react";

type GuidelineItemProps = {
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  title: string;
  description: string;
};

/**
 * A single capture-guideline row on the Welcome screen: an electric-green icon
 * tile beside a title + supporting copy.
 */
export function GuidelineItem({
  icon: Icon,
  title,
  description,
}: GuidelineItemProps) {
  return (
    <div className="flex items-start gap-4 py-5">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-surface-overlay text-accent-electric">
        <Icon className="h-6 w-6" />
      </span>
      <div>
        <h3 className="font-display text-lg font-bold text-on-surface-primary">
          {title}
        </h3>
        <p className="mt-1 font-sans text-body-md text-on-surface-secondary">
          {description}
        </p>
      </div>
    </div>
  );
}
