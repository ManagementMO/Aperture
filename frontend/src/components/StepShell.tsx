import type { ReactNode } from "react";

interface StepProps {
  index: number;
  title: string;
  state: "complete" | "active" | "pending";
  children: ReactNode;
}

/**
 * Numbered step block (Composio "Getting Started" pattern):
 *
 *   [1] Select your framework
 *   [2] Select language & mode
 *   [3] Setup your agent
 *   [4] Make your first call
 *
 * Use inside a flex column. State drives the dot color and the title weight.
 */
export function Step({ index, title, state, children }: StepProps) {
  const dotClass =
    state === "complete"
      ? "bg-primary text-primary-foreground"
      : state === "active"
        ? "bg-foreground text-background"
        : "bg-muted text-muted-foreground border border-border";

  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-semibold metric-value flex-none ${dotClass}`}
        >
          {state === "complete" ? "✓" : index}
        </div>
        <div className="flex-1 w-px bg-border my-1.5 min-h-[18px]" />
      </div>
      <div className="flex-1 pb-5">
        <p className={`text-[13px] mb-2 ${state === "pending" ? "text-muted-foreground" : "text-foreground font-medium"}`}>
          {title}
        </p>
        {children}
      </div>
    </div>
  );
}
