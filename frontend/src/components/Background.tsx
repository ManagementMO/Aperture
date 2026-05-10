/**
 * Linear/Vercel-style ambient background.
 *
 * Theme-aware: glows + dot grid use the foreground color via CSS vars so
 * they remain visible in both light and dark mode. The lime accent glow
 * pulls from --composio-lime which is already mode-mapped (bright lime on
 * dark, darker green on light).
 */

const GLOW_FG = "color-mix(in oklab, var(--foreground) 60%, transparent)";

export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {/* Brand glow — lime token adapts per mode */}
      <div
        aria-hidden
        className="absolute -top-32 -left-32 h-[640px] w-[640px] rounded-full opacity-[0.18] blur-3xl"
        style={{
          background:
            "radial-gradient(circle at center, var(--composio-lime) 0%, transparent 70%)",
        }}
      />
      {/* Cool secondary glow bottom-right — uses foreground so it inverts */}
      <div
        aria-hidden
        className="absolute -bottom-40 -right-40 h-[520px] w-[520px] rounded-full opacity-[0.06] blur-3xl"
        style={{
          background: `radial-gradient(circle at center, ${GLOW_FG} 0%, transparent 70%)`,
        }}
      />
      {/* Dot grid */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(color-mix(in oklab, var(--foreground) 8%, transparent) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
          maskImage:
            "radial-gradient(ellipse 60% 70% at 50% 40%, #000 30%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 60% 70% at 50% 40%, #000 30%, transparent 100%)",
        }}
      />
      {/* Top hairline */}
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background: `linear-gradient(90deg, transparent 0%, ${GLOW_FG} 25%, ${GLOW_FG} 75%, transparent 100%)`,
          opacity: 0.12,
        }}
      />
    </div>
  );
}
