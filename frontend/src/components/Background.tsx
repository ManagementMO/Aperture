/**
 * Linear/Vercel-style ambient background.
 *
 * Two layers:
 *   1. Subtle radial glow anchored top-left (mimics Linear's product surfaces).
 *   2. Faint dot grid that fades to nothing at the edges.
 *
 * Both are pointer-events:none and z-0 so all UI sits above without snagging.
 */
export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {/* Lime radial glow */}
      <div
        aria-hidden
        className="absolute -top-32 -left-32 h-[640px] w-[640px] rounded-full opacity-[0.18] blur-3xl"
        style={{
          background:
            "radial-gradient(circle at center, rgba(166,245,116,0.55) 0%, rgba(166,245,116,0) 70%)",
        }}
      />
      {/* Cool secondary glow bottom-right */}
      <div
        aria-hidden
        className="absolute -bottom-40 -right-40 h-[520px] w-[520px] rounded-full opacity-[0.07] blur-3xl"
        style={{
          background:
            "radial-gradient(circle at center, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0) 70%)",
        }}
      />
      {/* Dot grid */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(rgba(255,255,255,0.06) 1px, transparent 1px)",
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
          background:
            "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.08) 25%, rgba(255,255,255,0.08) 75%, transparent 100%)",
        }}
      />
    </div>
  );
}
