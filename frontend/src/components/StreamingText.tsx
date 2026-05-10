import { useEffect, useState } from "react";

/**
 * StreamingText — types out a full string character-by-character so the
 * Claude-style "thinking out loud" feel is preserved even though the
 * backend hands us the final answer in one shot. Speed is calibrated
 * to feel fast (≈900 chars/sec) but still perceptibly streaming.
 */
export function StreamingText({
  text,
  speed = 12, // ms per chunk
  chunk = 6,  // chars per tick
  className = "",
}: {
  text: string;
  speed?: number;
  chunk?: number;
  className?: string;
}) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    setShown(0);
  }, [text]);

  useEffect(() => {
    if (shown >= text.length) return;
    const id = window.setTimeout(
      () => setShown((s) => Math.min(text.length, s + chunk)),
      speed,
    );
    return () => window.clearTimeout(id);
  }, [shown, text, speed, chunk]);

  const done = shown >= text.length;
  return (
    <span className={className}>
      {text.slice(0, shown)}
      {!done && (
        <span
          className="inline-block w-[2px] h-[1em] align-text-bottom ml-[1px] bg-foreground/60"
          style={{ animation: "quava-pulse 1s ease-in-out infinite" }}
        />
      )}
    </span>
  );
}
