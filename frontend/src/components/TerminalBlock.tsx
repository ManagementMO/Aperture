import { useEffect, useState } from "react";

export interface TerminalLine {
  /** "$" lines are commands, anything else is shell output. */
  kind: "command" | "output" | "comment" | "spinner";
  text: string;
  /** Optional accent — render in lime. */
  accent?: boolean;
}

interface TerminalBlockProps {
  title?: string;
  lines: TerminalLine[];
  /** Auto-type the lines on mount instead of dumping them all at once. */
  animate?: boolean;
  className?: string;
}

/**
 * Mac-style terminal block matching Composio's hero-CLI aesthetic:
 *   $ composio search "file a bug"
 *   Found GITHUB_CREATE_ISSUE
 *   $ composio execute GITHUB_CREATE_ISSUE
 *   ✽ Composing...
 *
 * We use it on the Overview to render a real Quava CLI invocation
 * (vanilla_vs_aperture script).
 */
export function TerminalBlock({ title = "quava · zsh", lines, animate = true, className = "" }: TerminalBlockProps) {
  const [visible, setVisible] = useState(animate ? 0 : lines.length);

  useEffect(() => {
    if (!animate) return;
    if (visible >= lines.length) return;
    const id = window.setTimeout(() => setVisible((v) => v + 1), 350);
    return () => window.clearTimeout(id);
  }, [animate, visible, lines.length]);

  return (
    <div
      className={`rounded-xl border border-border overflow-hidden bg-[#0A0A0A] ${className}`}
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-black/40">
        <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F56]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#27C93F]" />
        <span className="ml-3 text-[11px] text-muted-foreground font-mono">{title}</span>
      </div>
      <pre className="p-4 text-[12px] font-mono leading-[1.55] text-foreground/90 overflow-auto">
        {lines.slice(0, visible).map((line, i) => (
          <div key={i} className="flex gap-2">
            {line.kind === "command" && <span className="text-primary select-none">$</span>}
            {line.kind === "comment" && <span className="text-muted-foreground select-none">#</span>}
            {line.kind === "spinner" && <span className="text-primary aperture-pulse">✽</span>}
            <span className={line.accent ? "text-primary" : line.kind === "output" ? "text-foreground/80" : ""}>
              {line.text}
            </span>
          </div>
        ))}
        {animate && visible < lines.length && (
          <div className="flex gap-2"><span className="text-primary aperture-pulse">▌</span></div>
        )}
      </pre>
    </div>
  );
}
