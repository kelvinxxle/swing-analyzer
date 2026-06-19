---
name: Apex Mechanics
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1b1b1c'
  surface-container: '#202020'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353535'
  on-surface: '#e5e2e1'
  on-surface-variant: '#c4c9ac'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#303030'
  outline: '#8e9379'
  outline-variant: '#444933'
  surface-tint: '#abd600'
  primary: '#ffffff'
  on-primary: '#283500'
  primary-container: '#c3f400'
  on-primary-container: '#556d00'
  inverse-primary: '#506600'
  secondary: '#c8c6c5'
  on-secondary: '#313030'
  secondary-container: '#4a4949'
  on-secondary-container: '#bab8b7'
  tertiary: '#ffffff'
  on-tertiary: '#21323e'
  tertiary-container: '#d2e5f5'
  on-tertiary-container: '#556774'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#c3f400'
  primary-fixed-dim: '#abd600'
  on-primary-fixed: '#161e00'
  on-primary-fixed-variant: '#3c4d00'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474646'
  tertiary-fixed: '#d2e5f5'
  tertiary-fixed-dim: '#b6c9d8'
  on-tertiary-fixed: '#0b1d29'
  on-tertiary-fixed-variant: '#374956'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353535'
  surface-base: '#121212'
  surface-elevated: '#1E1E1E'
  surface-overlay: '#2A2A2A'
  on-surface-primary: '#FFFFFF'
  on-surface-secondary: '#A1A1A1'
  accent-electric: '#CCFF00'
  status-error: '#FF4444'
  status-warning: '#FFB800'
typography:
  headline-xl:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-label:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  button-text:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  container-max-width: 800px
---

## Brand & Style

This design system is engineered for the high-performance athlete and the data-driven amateur. The brand personality is **direct, expert, and authoritative**, moving away from "friendly coaching" toward "precision diagnostics." It evokes the feeling of a professional laboratory or a premium performance garage.

The design style is **Modern Corporate with a High-Contrast/Data-Driven edge**. It utilizes deep charcoal foundations to minimize visual noise, allowing vibrant "Electric Green" accents to highlight critical performance data and calls to action. The aesthetic is "Dark Mode First," reflecting the focused environment of a high-tech training facility. Layouts are rigorous and structured, favoring clarity and speed of information over decorative flourishes.

## Colors

The palette is anchored in a three-tier dark gray system to create depth without relying on traditional shadows.

- **Primary (Electric Green):** Reserved exclusively for active states, primary buttons, and successful performance metrics.
- **Surface Base:** The foundational layer for the application background.
- **Surface Elevated:** Used for cards and secondary containers to distinguish them from the base.
- **Typography:** Primary text is pure white for maximum legibility against dark backgrounds. Secondary text uses a desaturated gray to maintain visual hierarchy.
- **Status Colors:** Red is used strictly for upload rejections or "Bad Input" errors; yellow is used for "Minor Flaw" warnings.

## Typography

The typographic system prioritizes impact and readability under various lighting conditions (e.g., at the driving range).

- **Headlines:** Use **Hanken Grotesk** with heavy weights (700+) and tight letter spacing to convey strength and mechanical precision.
- **Body:** **Inter** is used for its exceptional legibility in dark mode, particularly for "Fix Tips" and technical descriptions.
- **Technical/Data:** **JetBrains Mono** is introduced for labels and technical metadata (e.g., frame counts, angle degrees) to reinforce the "Sport Tech" and data-driven nature of the analysis.
- **Hierarchy:** Use all-caps sparingly, primarily for small labels and buttons to create a "UI-as-an-instrument" feel.

## Layout & Spacing

The layout is built on a **rigid 4px baseline grid** to ensure mathematical consistency. 

- **Grid Model:** Use a 12-column fluid grid for desktop and a 4-column grid for mobile. Because the app is focused on a "One-shot" flow (Upload → Analysis), the content should be centrally aligned with a maximum container width to prevent the eyes from scanning too wide on desktop screens.
- **Density:** The spacing is "Tight but purposeful." Use 16px (4 units) for standard gutters and internal card padding. Use 32px (8 units) to separate distinct sections of the analysis report.
- **Mobile First:** Given the use case (on the golf course), the layout must be optimized for single-hand use, with primary CTAs placed in the "thumb zone" at the bottom of the screen.

## Elevation & Depth

In this dark-themed system, depth is communicated through **tonal layering** rather than shadows. 

- **Level 0 (Base):** `#121212` - The main canvas.
- **Level 1 (Cards/Containers):** `#1E1E1E` - Used for the upload area and flaw descriptions.
- **Level 2 (Modals/Overlays):** `#2A2A2A` - Used for rejection notices or temporary tooltips.
- **Accents:** High-frequency interactions use a 1px solid border of the primary color (`#CCFF00`) instead of a shadow to indicate "active" or "focused" states. This reinforces the high-contrast, technical aesthetic.

## Shapes

The shape language is **Soft (0.25rem)**. 

While the aesthetic is aggressive and professional, subtle rounding on corners prevents the UI from feeling dated or overly "brutalist." 
- **Buttons and Inputs:** Use a 4px (0.25rem) radius.
- **Large Cards:** Use an 8px (0.5rem) radius to create a clear container for analysis results.
- **Strictness:** Do not use pills or circles unless for icon containers. The square-adjacent corners reflect the precision of the data being analyzed.

## Components

- **Primary Buttons:** High-contrast background (`#CCFF00`) with black text. On hover, use a slight brightness shift. Buttons should be full-width on mobile to facilitate easy tapping.
- **Upload Cards:** Use a dashed 1px border (`#A1A1A1`) in the empty state. When a video is selected, transition to a solid `#CCFF00` border to indicate readiness.
- **Analysis Result Cards:** Each "Flaw" is presented in a Level 1 container. Use a vertical "Status Bar" on the left edge of the card (Electric Green for success, Yellow for flaws) to allow for quick scanning.
- **Data Labels:** Small, monospaced text in all-caps, used for "ANGLE," "FLAW TYPE," or "TIMESTAMP."
- **Feedback Alerts:** In case of "Bad Input," use a high-visibility banner at the top of the viewport with `#FF4444` background and white text.
- **Progress Indicators:** Use a linear, high-contrast bar (Electric Green on Dark Gray) for video processing states. Avoid circular "spinners" to maintain the linear, data-driven feel.