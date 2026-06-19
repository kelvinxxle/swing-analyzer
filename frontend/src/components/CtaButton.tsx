import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type CommonProps = {
  children: ReactNode;
  className?: string;
};

type LinkCta = CommonProps & {
  href: string;
};

type ButtonCta = CommonProps & ButtonHTMLAttributes<HTMLButtonElement>;

const baseClasses =
  "flex w-full items-center justify-center gap-2 rounded bg-accent-electric px-6 py-4 font-display text-button-text uppercase tracking-wide text-surface-base transition hover:brightness-110 active:scale-[0.99] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-electric";

/**
 * Primary call-to-action: full-width, high-contrast electric-green, intended
 * for the bottom "thumb zone" on mobile. Renders a Next.js <Link> when `href`
 * is provided, otherwise a <button>.
 */
export function CtaButton(props: LinkCta | ButtonCta) {
  if ("href" in props && props.href) {
    const { href, children, className } = props;
    return (
      <Link href={href} className={`${baseClasses} ${className ?? ""}`}>
        {children}
      </Link>
    );
  }

  const { children, className, ...rest } = props;
  return (
    <button className={`${baseClasses} ${className ?? ""}`} {...rest}>
      {children}
    </button>
  );
}
