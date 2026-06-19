import type { Config } from "tailwindcss";

/**
 * Design tokens from docs/design/design-system.md — codename "Apex Mechanics".
 * Dark-mode-first, high-contrast, data-driven. Electric green is the accent.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#131313",
          base: "#121212",
          dim: "#131313",
          bright: "#393939",
          elevated: "#1e1e1e",
          overlay: "#2a2a2a",
          variant: "#353535",
          "container-lowest": "#0e0e0e",
          "container-low": "#1b1b1c",
          container: "#202020",
          "container-high": "#2a2a2a",
          "container-highest": "#353535",
        },
        "on-surface": {
          DEFAULT: "#e5e2e1",
          variant: "#c4c9ac",
          primary: "#ffffff",
          secondary: "#a1a1a1",
        },
        primary: {
          DEFAULT: "#ffffff",
          container: "#c3f400",
          fixed: "#c3f400",
          "fixed-dim": "#abd600",
        },
        "on-primary": {
          DEFAULT: "#283500",
          container: "#556d00",
        },
        secondary: {
          DEFAULT: "#c8c6c5",
          container: "#4a4949",
        },
        "on-secondary": {
          DEFAULT: "#313030",
          container: "#bab8b7",
        },
        tertiary: {
          DEFAULT: "#ffffff",
          container: "#d2e5f5",
        },
        outline: {
          DEFAULT: "#8e9379",
          variant: "#444933",
        },
        accent: {
          electric: "#ccff00",
        },
        "surface-tint": "#abd600",
        status: {
          error: "#ff4444",
          warning: "#ffb800",
        },
        error: {
          DEFAULT: "#ffb4ab",
          container: "#93000a",
        },
        "on-error": {
          DEFAULT: "#690005",
          container: "#ffdad6",
        },
      },
      fontFamily: {
        display: ["var(--font-hanken)", "system-ui", "sans-serif"],
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      fontSize: {
        "headline-xl": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "800" }],
        "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "700" }],
        "headline-lg-mobile": ["24px", { lineHeight: "32px", fontWeight: "700" }],
        "body-md": ["16px", { lineHeight: "24px" }],
        "body-sm": ["14px", { lineHeight: "20px" }],
        "data-label": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "500" }],
        "button-text": ["16px", { lineHeight: "16px", letterSpacing: "0.02em", fontWeight: "600" }],
      },
      borderRadius: {
        sm: "0.125rem",
        DEFAULT: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px",
      },
      maxWidth: {
        container: "800px",
      },
      spacing: {
        gutter: "16px",
        "margin-mobile": "16px",
        "margin-desktop": "32px",
      },
    },
  },
  plugins: [],
};

export default config;
