/**
 * Cursor-style ambient background — flat, subtle, almost invisible.
 * No glows, no gradients, just the faintest grain so the surface
 * doesn't feel like a flat #0A0A0A void. One hairline at the top.
 */
export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {/* Subtle dot grid that fades to nothing at the edges */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(color-mix(in oklab, var(--foreground) 4%, transparent) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
          maskImage:
            "radial-gradient(ellipse 70% 80% at 50% 30%, #000 30%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 70% 80% at 50% 30%, #000 30%, transparent 100%)",
        }}
      />
      {/* Top hairline */}
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, color-mix(in oklab, var(--foreground) 8%, transparent) 50%, transparent 100%)",
        }}
      />
    </div>
  );
}
