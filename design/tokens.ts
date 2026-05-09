/**
 * Ark Design Tokens — TypeScript mirror of tokens.css.
 *
 * Drop into `lib/design.ts` (web) or `src/lib/design.ts` (desktop).
 * Use for inline styles, JS-driven animations, and chart configs.
 *
 * MUST stay in lockstep with tokens.css — CI diff test (tests/design-tokens.test.ts)
 * fails on drift. See ark/design/ARK_DESIGN_BIBLE.md §14.3.
 */

export const T = {
  /* ---------------------------------------------------------------- COLOR */
  color: {
    dark: {
      bg: "#000000",
      surface: "#0A0A0A",
      surfaceContainer: "#111111",
      surfaceContainerHigh: "#161616",
      surfaceContainerHighest: "#1A1A1A",
      raisedHover: "#222222",
      fg: "#FFFFFF",
      fg87: "rgba(255,255,255,0.87)",
      fg60: "rgba(255,255,255,0.60)",
      fg38: "rgba(255,255,255,0.38)",
      fg30: "rgba(255,255,255,0.30)",
      outline: "rgba(255,255,255,0.16)",
      outlineVariant: "rgba(255,255,255,0.08)",
      stateHover: "rgba(255,255,255,0.04)",
      stateFocus: "rgba(255,255,255,0.06)",
      statePressed: "rgba(255,255,255,0.08)",
      stateSelected: "rgba(255,255,255,0.10)",
      stateDragged: "rgba(255,255,255,0.12)",
      tertiary: "#888888",
      scrim: "rgba(0,0,0,0.6)",
      ring: "rgba(255,255,255,0.6)",
    },
    light: {
      bg: "#FFFFFF",
      surface: "#F8F8F8",
      surfaceContainer: "#F0F0F0",
      surfaceContainerHigh: "#E8E8E8",
      surfaceContainerHighest: "#E0E0E0",
      raisedHover: "#D8D8D8",
      fg: "#000000",
      fg87: "rgba(0,0,0,0.87)",
      fg60: "rgba(0,0,0,0.60)",
      fg38: "rgba(0,0,0,0.38)",
      fg30: "rgba(0,0,0,0.30)",
      outline: "rgba(0,0,0,0.16)",
      outlineVariant: "rgba(0,0,0,0.08)",
      stateHover: "rgba(0,0,0,0.04)",
      stateFocus: "rgba(0,0,0,0.06)",
      statePressed: "rgba(0,0,0,0.08)",
      stateSelected: "rgba(0,0,0,0.10)",
      stateDragged: "rgba(0,0,0,0.12)",
      tertiary: "#666666",
      scrim: "rgba(0,0,0,0.4)",
      ring: "rgba(0,0,0,0.6)",
    },
  },

  /* -------------------------------------------------------------- SPACING */
  space: {
    0: "0px",
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    5: "20px",
    6: "24px",
    8: "32px",
    10: "40px",
    12: "48px",
    16: "64px",
    20: "80px",
    24: "96px",
  },

  /* --------------------------------------------------------------- RADIUS */
  radius: {
    none: "0px",
    sm: "4px",
    md: "8px",
    lg: "12px",
    xl: "16px",
    "2xl": "24px",
    full: "9999px",
  },

  /* ------------------------------------------------------------- TYPOGRAPHY */
  font: {
    sans: '"Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"Geist Mono", "JetBrains Mono", "SF Mono", "Fira Code", monospace',
  },
  text: {
    displayLg: { size: "3.5625rem", line: "4rem", weight: 600, tracking: "-0.25px" },
    displayMd: { size: "2.8125rem", line: "3.25rem", weight: 600, tracking: "0" },
    displaySm: { size: "2.25rem", line: "2.75rem", weight: 600, tracking: "0" },
    headlineLg: { size: "2rem", line: "2.5rem", weight: 600, tracking: "0" },
    headlineMd: { size: "1.75rem", line: "2.25rem", weight: 600, tracking: "0" },
    headlineSm: { size: "1.5rem", line: "2rem", weight: 500, tracking: "0" },
    titleLg: { size: "1.375rem", line: "1.75rem", weight: 500, tracking: "0" },
    titleMd: { size: "1rem", line: "1.5rem", weight: 500, tracking: "0.15px" },
    titleSm: { size: "0.875rem", line: "1.25rem", weight: 500, tracking: "0.1px" },
    bodyLg: { size: "1rem", line: "1.5rem", weight: 400, tracking: "0.5px" },
    bodyMd: { size: "0.875rem", line: "1.25rem", weight: 400, tracking: "0.25px" },
    bodySm: { size: "0.75rem", line: "1rem", weight: 400, tracking: "0.4px" },
    labelLg: { size: "0.875rem", line: "1.25rem", weight: 500, tracking: "0.1px" },
    labelMd: { size: "0.75rem", line: "1rem", weight: 500, tracking: "0.5px" },
    labelSm: { size: "0.6875rem", line: "1rem", weight: 500, tracking: "0.5px" },
  },

  /* --------------------------------------------------------------- Z-INDEX */
  z: {
    base: 0,
    raised: 10,
    dropdown: 1000,
    sticky: 1020,
    overlay: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
    toast: 1080,
    command: 1090,
  },

  /* ---------------------------------------------------------------- MOTION */
  motion: {
    duration: {
      fast: "150ms",
      base: "200ms",
      slow: "300ms",
      threatBar: "500ms",
      sparkline: "800ms",
    },
    ease: {
      out: "cubic-bezier(0.2, 0, 0, 1)",
      in: "cubic-bezier(0.4, 0, 1, 1)",
      inOut: "cubic-bezier(0.4, 0, 0.2, 1)",
      linear: "linear",
    },
  },

  /* ------------------------------------------------------- BREAKPOINTS (px) */
  breakpoints: {
    xs: 0,
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    "2xl": 1536,
  },

  /* -------------------------------------------------- THREAT HIERARCHY (§3.3) */
  threat: {
    critical: { textOpacity: 1.0, weight: 600, borderOpacity: 0.15, surfaceTint: "rgba(255,255,255,0.02)" },
    high:     { textOpacity: 0.87, weight: 600, borderOpacity: 0.10, surfaceTint: "transparent" },
    medium:   { textOpacity: 0.60, weight: 500, borderOpacity: 0.08, surfaceTint: "transparent" },
    low:      { textOpacity: 0.38, weight: 400, borderOpacity: 0.06, surfaceTint: "transparent" },
    info:     { textOpacity: 0.60, weight: 400, borderOpacity: 0.08, surfaceTint: "transparent" },
  },
} as const;

export type ArkTokens = typeof T;
export type ThreatLevel = keyof typeof T.threat;
