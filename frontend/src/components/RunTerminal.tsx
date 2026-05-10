/**
 * RunTerminal — a Composio-playground-style live terminal that mirrors
 * each tool call the agent runs, side-by-side with the agent reply panel.
 *
 * Visual language is borrowed from Composio's playground: a tree of
 * pipes (├ │ └) that lets the eye scan tool calls vertically. We add
 * Quava-specific lines underneath each call:
 *
 *   COMPOSIO_SEARCH_TOOLS                     ← what Composio shipped
 *     ├ raw          1,908 tok
 *     ├ aperture       655 tok   -65.7%
 *     ├ cache        miss · 1,347 ms
 *     ├ tier         full
 *     └ [ compare ]                           ← opens before/after dialog
 *
 * The "compare" button is wired by the parent so it can open whatever
 * dialog it wants (we keep this component presentation-only).
 */

import { Terminal as TerminalIcon } from "lucide-react";

export interface RunTerminalStep {
  tool: string;
  successful?: boolean;
  raw_tokens: number;
  sent_tokens: number;
  saved_percent?: number;
  elapsed_ms?: number;
  cache_status?: "miss" | "hit" | "write_uncached" | "blocked_write";
  cache_age_seconds?: number;
  composio_cost_avoided_usd?: number;
  tier?: "full" | "degraded" | "passthrough";
  ultra_summary?: string | null;
  strategy?: string;
  llm_format?: string;
}

interface RunTerminalProps {
  running: boolean;
  steps: RunTerminalStep[];
  totalRawTokens?: number;
  totalSentTokens?: number;
  totalElapsedMs?: number;
  costSavedUsd?: number;
  servedFromCache?: boolean;
  onCompareStep: (index: number) => void;
}

function fmtNum(n: number): string {
  return n.toLocaleString();
}

function fmtPct(n?: number): string {
  if (n === undefined || n === null) return "—";
  return `${n >= 0 ? "-" : "+"}${Math.abs(n).toFixed(1)}%`;
}

export function RunTerminal({
  running,
  steps,
  totalRawTokens,
  totalSentTokens,
  totalElapsedMs,
  costSavedUsd,
  servedFromCache,
  onCompareStep,
}: RunTerminalProps) {
  // Steps are now streamed by the parent — render them as they arrive.
  // No fake reveal animation; if you see a step it just landed.
  const visible = steps;
  const totalSavedPct =
    totalRawTokens && totalSentTokens
      ? Math.round((1 - totalSentTokens / totalRawTokens) * 1000) / 10
      : null;

  return (
    <div className="rounded-xl border border-border overflow-hidden bg-[#0A0A0A] flex flex-col h-full">
      {/* Mac-style title bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-black/40 flex-none">
        <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F56]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#27C93F]" />
        <span className="ml-3 text-[11px] text-muted-foreground font-mono flex items-center gap-1.5">
          <TerminalIcon className="w-3 h-3" />
          quava · live tool calls
        </span>
        {running && (
          <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-primary font-mono">
            <span className="aperture-pulse">●</span> running
          </span>
        )}
      </div>

      <div className="p-3 text-[11.5px] font-mono leading-[1.6] text-foreground/85 overflow-auto flex-1 min-h-[300px]">
        {/* Empty state */}
        {steps.length === 0 && !running && (
          <pre className="text-muted-foreground/70">
            <span className="text-primary select-none">$</span> quava run --watch{"\n"}
            <span className="text-muted-foreground/50">
              ↳ idle. send an ask to see tool calls land here.
            </span>
          </pre>
        )}

        {running && (
          <pre className="text-muted-foreground">
            <span className="text-primary select-none">$</span> dispatching to composio…{"\n"}
            <span className="text-primary aperture-pulse">▌</span>
          </pre>
        )}

        {/* Tool calls */}
        {visible.map((step, i) => (
          <StepBlock
            key={i}
            step={step}
            isLast={i === steps.length - 1}
            onCompare={() => onCompareStep(i)}
          />
        ))}

        {/* Footer summary once the run is done */}
        {!running && steps.length > 0 && (
          <pre className="mt-2 text-foreground/80">
            <span className="text-primary">└</span>{" "}
            <span className="text-primary">✓</span>{" "}
            done · {steps.length} tool call{steps.length === 1 ? "" : "s"}
            {totalElapsedMs !== undefined && ` · ${totalElapsedMs.toLocaleString()} ms`}
            {totalSavedPct !== null && (
              <>
                {" · "}
                <span className="text-primary">
                  {fmtPct(totalSavedPct)} smaller
                </span>
              </>
            )}
            {costSavedUsd !== undefined && costSavedUsd > 0 && (
              <>
                {" · "}
                <span className="text-primary">
                  ${costSavedUsd.toFixed(4)} saved
                </span>
              </>
            )}
            {servedFromCache && (
              <>
                {"\n  "}
                <span className="text-primary">★</span> entire answer
                served from result cache · $0.000000
              </>
            )}
          </pre>
        )}
      </div>
    </div>
  );
}

function StepBlock({
  step,
  isLast,
  onCompare,
}: {
  step: RunTerminalStep;
  isLast: boolean;
  onCompare: () => void;
}) {
  const cacheLabel = (() => {
    switch (step.cache_status) {
      case "hit":
        return `hit · ${step.cache_age_seconds ?? 0}s old`;
      case "miss":
        return "miss";
      case "write_uncached":
        return "write · uncached";
      case "blocked_write":
        return "blocked (read-only)";
      default:
        return "—";
    }
  })();
  const branchTop = isLast ? "└" : "├";
  const branchInner = isLast ? "  " : "│ ";

  return (
    <div className="mb-1">
      {/* tool header */}
      <div className="flex items-baseline gap-2">
        <span className="text-primary select-none">{branchTop}</span>
        <span className="text-foreground font-semibold">{step.tool}</span>
        {step.successful === false && (
          <span className="text-rose-300 text-[10px] uppercase tracking-widest">
            error
          </span>
        )}
        {step.cache_status === "hit" && (
          <span className="ml-1 px-1.5 py-0 rounded border border-primary/30 bg-primary/10 text-primary text-[9px] font-mono uppercase tracking-wider">
            cache hit · ${(step.composio_cost_avoided_usd ?? 0).toFixed(4)} saved
          </span>
        )}
      </div>

      {/* attributes — Composio's tree style */}
      <Attr branch={branchInner} label="raw" value={`${fmtNum(step.raw_tokens)} tok`} />
      <Attr
        branch={branchInner}
        label="quava"
        value={`${fmtNum(step.sent_tokens)} tok`}
        trailing={
          step.saved_percent !== undefined ? (
            <span
              className={
                step.saved_percent >= 0
                  ? "text-primary"
                  : "text-amber-300"
              }
            >
              {fmtPct(step.saved_percent)}
            </span>
          ) : null
        }
      />
      {step.strategy && (
        <Attr
          branch={branchInner}
          label="encoding"
          value={`${step.strategy}/${step.llm_format ?? "json"}`}
        />
      )}
      <Attr branch={branchInner} label="cache" value={cacheLabel} />
      {step.elapsed_ms !== undefined && (
        <Attr
          branch={branchInner}
          label="latency"
          value={`${Math.round(step.elapsed_ms).toLocaleString()} ms`}
        />
      )}
      {step.tier && step.tier !== "full" && (
        <Attr
          branch={branchInner}
          label="tier"
          value={step.tier}
          trailing={
            <span className="text-amber-300 text-[10px] uppercase tracking-widest">
              degraded
            </span>
          }
        />
      )}
      {step.ultra_summary && (
        <Attr
          branch={branchInner}
          label="summary"
          value={step.ultra_summary}
          mono
        />
      )}

      {/* Compare button */}
      <div className="flex items-baseline gap-2">
        <span className="text-primary select-none">{branchInner}</span>
        <button
          type="button"
          onClick={onCompare}
          className="inline-flex items-center px-1.5 py-0.5 rounded border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors text-[10px] uppercase tracking-wider"
        >
          ⊞ compare
        </button>
        <span className="text-muted-foreground/50 text-[10px]">
          composio raw ↔ quava sent
        </span>
      </div>
    </div>
  );
}

function Attr({
  branch,
  label,
  value,
  trailing,
  mono,
}: {
  branch: string;
  label: string;
  value: string;
  trailing?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-primary/60 select-none">{branch}</span>
      <span className="text-muted-foreground w-16 inline-block">{label}</span>
      <span
        className={
          mono
            ? "text-foreground/85 truncate"
            : "text-foreground/85"
        }
        style={mono ? { maxWidth: "240px" } : undefined}
        title={mono ? value : undefined}
      >
        {value}
      </span>
      {trailing}
    </div>
  );
}
