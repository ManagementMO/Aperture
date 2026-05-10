import { useEffect, useState } from "react";
import { apiPostStream, describeApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowUp, Check, ChevronDown, ChevronUp, Sparkles, Terminal as TerminalIcon, X } from "lucide-react";
import { ComposingSpinner } from "@/components/ComposingSpinner";
import { TerminalBlock, type TerminalLine } from "@/components/TerminalBlock";
import { RunTerminal } from "@/components/RunTerminal";
import { CompareDialog } from "@/components/CompareDialog";

interface Step {
  tool: string;
  tool_label?: string;
  arguments?: Record<string, unknown>;
  successful?: boolean;
  error?: string | null;
  raw_tokens: number;
  sent_tokens: number;
  saved_tokens: number;
  saved_percent?: number;
  raw_bytes?: number;
  sent_bytes?: number;
  strategy?: string;
  llm_format?: string;
  omitted_fields?: string[];
  policy_reason_counts?: Record<string, number>;
  policy_promotions?: { name: string; reason: string }[];
  classifier_used?: boolean;
  classifier_keeps?: string[];
  raw_preview?: string;
  compressed_preview?: string;
  elapsed_ms?: number;
  ultra_summary?: string | null;
  tier?: "full" | "degraded" | "passthrough";
  cache_status?: "miss" | "hit" | "write_uncached" | "blocked_write";
  cache_age_seconds?: number;
  composio_cost_avoided_usd?: number;
  effort_mode?: EffortMode;
  compression_mode?: string;
  breakdown?: TokenBreakdown;
}

interface TokenBreakdown {
  token_math: string;
  strategy: string;
  llm_format: string;
  remaining_sentence: string;
  all_api_fields_removed: string[];
  items: BreakdownItem[];
}

interface BreakdownItem {
  label: string;
  tokens: number;
  kind: "saved" | "added";
  description: string;
  fields?: string[];
  occurrences?: number;
  paths?: string[];
  details?: string[];
  format?: string;
  json_tokens?: number;
  sent_tokens?: number;
}

interface Summary {
  tool_calls: number;
  raw_tokens: number;
  sent_tokens: number;
  saved_tokens: number;
  saved_percent: number;
  elapsed_ms: number;
  cost_before_usd: number;
  cost_after_usd: number;
  cost_saved_usd: number;
  composio_calls_made?: number;
  composio_calls_avoided?: number;
  composio_cost_avoided_usd?: number;
}

interface CostBlock {
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  raw_input_tokens: number;
  actual_usd: number;
  counterfactual_usd: number;
  saved_usd: number;
  cache_hit_rate: number;
}

interface RunResult {
  ask: string;
  answer: string;
  model: string;
  effort_mode: EffortMode;
  iterations: number;
  stopped_reason: string;
  error: string | null;
  summary: Summary;
  cost?: CostBlock | null;
  steps: Step[];
  served_from_cache?: boolean;
  cached_age_seconds?: number;
  cache?: ToolCacheStats;
}

interface RunHistoryEntry {
  ts: number;
  ask: string;
  answer: string;
  model: string;
  effort_mode?: EffortMode;
  summary: Summary;
  steps: Step[];
  cost?: CostBlock | null;
  served_from_cache?: boolean;
}

interface ToolCacheEntry {
  tool: string;
  arguments?: Record<string, unknown>;
  cache_scope?: string;
  cache_key_hash?: string;
  age_seconds?: number;
  ttl_remaining_seconds?: number | null;
}

interface ToolCacheStats {
  entries: number;
  tool_entries?: number;
  items?: ToolCacheEntry[];
}

const HISTORY_KEY = "aperture.runs.v1";
const HISTORY_LIMIT = 30;
type EffortMode = "off" | "aggressive" | "low" | "medium" | "high" | "auto";

const MODES: { value: EffortMode; label: string; detail: string }[] = [
  { value: "off", label: "Off", detail: "raw tool output" },
  { value: "aggressive", label: "Aggressive", detail: "maximum compression" },
  { value: "low", label: "Low", detail: "smallest context" },
  { value: "medium", label: "Medium", detail: "balanced default" },
  { value: "high", label: "High", detail: "more detail kept" },
  { value: "auto", label: "Auto", detail: "per-tool routing" },
];

function appendRunToHistory(result: RunResult): void {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    const list: RunHistoryEntry[] = raw ? JSON.parse(raw) : [];
    list.unshift({
      ts: Date.now(),
      ask: result.ask,
      answer: result.answer,
      model: result.model,
      effort_mode: result.effort_mode,
      summary: result.summary,
      steps: result.steps,
      cost: result.cost,
      served_from_cache: result.served_from_cache,
    });
    const trimmed = list.slice(0, HISTORY_LIMIT);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed));
    window.dispatchEvent(new CustomEvent("aperture:run", { detail: trimmed[0] }));
  } catch {
    // localStorage may be disabled — skip silently
  }
}

const PROMPTS: { label: string; ask: string }[] = [
  { label: "Repo overview", ask: "Get the composiohq/composio repo overview — stars, language, open issue count" },
  { label: "Recent commits", ask: "List the last 3 commits on the composiohq/composio main branch" },
  { label: "Inbox scan", ask: "Pull my last 3 Gmail emails and summarize them" },
  { label: "Sheet read", ask: "Read the first 50 rows of my Google Sheet" },
];

export default function Run() {
  const [ask, setAsk] = useState("");
  const [effortMode, setEffortMode] = useState<EffortMode>("medium");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openSteps, setOpenSteps] = useState<Set<number>>(new Set());
  const [liveSteps, setLiveSteps] = useState<Step[]>([]);
  const [compareIndex, setCompareIndex] = useState<number | null>(null);
  const [terminalOpen, setTerminalOpen] = useState<boolean>(false);

  // The cache panel was dropped from the redesign — cache info now shows
  // inline on each tool chip. We keep a no-op refresh for the post-submit
  // hook so we can wire a future affordance back in without a refactor.
  const refreshToolCache = async (): Promise<void> => {};

  useEffect(() => {
    const initializeDemoCache = async (): Promise<void> => {
      await refreshToolCache();
    };

    void initializeDemoCache();
  }, []);


  const submit = async (): Promise<void> => {
    const trimmed = ask.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setResult(null);
    setError(null);
    setOpenSteps(new Set());
    setLiveSteps([]);
    try {
      // Streaming submit — every tool call lands in the right-hand
      // terminal as it completes, not at the end of the run.
      const partials: Step[] = [];
      let finalResult: RunResult | null = null as RunResult | null;

      await apiPostStream(
        "/api/demo/run/stream",
        { ask: trimmed, effort_mode: effortMode },
        (evt) => {
          const kind = evt.kind as string;
          if (kind === "step") {
            // Strip 'kind' so the rest is the step shape.
            const { kind: _k, ...stepData } = evt;
            partials.push(stepData as unknown as Step);
            setLiveSteps([...partials]);
          } else if (kind === "final") {
            const { kind: _k, ...finalData } = evt;
            const full = finalData as unknown as Record<string, unknown>;
            const sentTokens = (full.total_sent_tokens as number) ?? 0;
            const rawTokens = (full.total_raw_tokens as number) ?? 0;
            const savedPct =
              rawTokens > 0
                ? Math.round((1 - sentTokens / rawTokens) * 1000) / 10
                : 0;
            finalResult = {
              ask: trimmed,
              answer: (full.answer as string) ?? "",
              model: (full.model as string) ?? "",
              effort_mode: effortMode,
              iterations: (full.iterations as number) ?? 0,
              stopped_reason: (full.stopped_reason as string) ?? "",
              error: (full.error as string | null) ?? null,
              served_from_cache: (full.served_from_cache as boolean) ?? false,
              cached_age_seconds: (full.cached_age_seconds as number) ?? 0,
              cost: (full.cost as CostBlock | null) ?? null,
              steps: partials,
              summary: {
                tool_calls: partials.length,
                raw_tokens: rawTokens,
                sent_tokens: sentTokens,
                saved_tokens: Math.max(0, rawTokens - sentTokens),
                saved_percent: savedPct,
                elapsed_ms: (full.total_elapsed_ms as number) ?? 0,
                cost_before_usd:
                  ((full.cost as CostBlock | null)?.counterfactual_usd) ?? 0,
                cost_after_usd:
                  ((full.cost as CostBlock | null)?.actual_usd) ?? 0,
                cost_saved_usd:
                  ((full.cost as CostBlock | null)?.saved_usd) ?? 0,
                composio_calls_made:
                  (full.composio_calls_made as number) ?? 0,
                composio_calls_avoided:
                  (full.composio_calls_avoided as number) ?? 0,
                composio_cost_avoided_usd:
                  (full.composio_cost_avoided_usd as number) ?? 0,
              },
            };
            setResult(finalResult);
          } else if (kind === "error") {
            setError((evt.message as string) ?? "stream error");
          }
        },
      );

      if (finalResult) {
        // append to history once the run is settled
        appendRunToHistory(finalResult);
        if (finalResult.error) setError(finalResult.error);
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      void refreshToolCache();
      setRunning(false);
    }
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void submit();
  };

  const toggleStep = (i: number) => {
    setOpenSteps((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const hasConversation = running || liveSteps.length > 0 || result || error;
  const stepsForTerminal = (running ? liveSteps : (result?.steps ?? liveSteps)) as RunTerminalStepData[];

  // ChatGPT-style pill input: single auto-growing textarea, mode chip on
  // the right, round white send button, no chunky toolbar.
  const InputCard = (
    <div className="relative rounded-[28px] bg-foreground/[0.04] hover:bg-foreground/[0.05] focus-within:bg-foreground/[0.055] transition-colors px-2 pt-2.5 pb-2">
      <div className="flex items-end gap-2">
        <textarea
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask anything"
          rows={1}
          className="flex-1 resize-none bg-transparent px-3 pt-1.5 pb-1.5 text-[15px] leading-[1.5] outline-none placeholder:text-muted-foreground/60 max-h-[200px] overflow-y-auto"
          autoFocus
          style={{ minHeight: "28px" }}
          onInput={(e) => {
            const ta = e.currentTarget;
            ta.style.height = "auto";
            ta.style.height = Math.min(200, ta.scrollHeight) + "px";
          }}
        />
        <div className="flex items-center gap-1.5 flex-none pb-0.5">
          <ModePill
            modes={MODES}
            value={effortMode}
            onChange={setEffortMode}
            disabled={running}
          />
          <button
            type="button"
            onClick={() => setTerminalOpen((v) => !v)}
            title={terminalOpen ? "Hide tool calls" : "Show tool calls"}
            className={`inline-flex items-center justify-center h-8 w-8 rounded-full transition-colors ${
              terminalOpen
                ? "bg-foreground/15 text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06]"
            }`}
          >
            <TerminalIcon className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!ask.trim() || running}
            className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-foreground text-background hover:bg-foreground/90 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            {running ? <ComposingSpinner size="sm" /> : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="relative">
      <CompareDialog
        open={compareIndex !== null}
        step={
          compareIndex !== null
            ? (result?.steps[compareIndex] ?? liveSteps[compareIndex] ?? null)
            : null
        }
        onClose={() => setCompareIndex(null)}
      />

      {/* Slide-out terminal — Claude-style: hidden until requested */}
      {terminalOpen && (
        <aside className="fixed top-14 right-0 bottom-0 w-[420px] z-30 border-l border-border/40 bg-background/95 backdrop-blur-md flex flex-col">
          <div className="flex items-center justify-between h-11 px-4 border-b border-border/30 flex-none">
            <div className="flex items-center gap-2 text-[12px]">
              <TerminalIcon className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="font-medium">Tool calls</span>
              {liveSteps.length > 0 && (
                <span className="text-muted-foreground/60 num">
                  · {liveSteps.length}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setTerminalOpen(false)}
              className="inline-flex items-center justify-center w-7 h-7 rounded-md text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground transition-colors"
              aria-label="Close terminal"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex-1 overflow-hidden">
            <RunTerminal
              running={running}
              steps={stepsForTerminal}
              totalRawTokens={result?.summary.raw_tokens}
              totalSentTokens={result?.summary.sent_tokens}
              totalElapsedMs={result?.summary.elapsed_ms}
              costSavedUsd={result?.summary.cost_saved_usd}
              servedFromCache={result?.served_from_cache}
              onCompareStep={(i) => setCompareIndex(i)}
            />
          </div>
        </aside>
      )}

      <div
        className={`transition-[padding] duration-200 ${
          terminalOpen ? "pr-[440px]" : ""
        }`}
      >
      <div className="mx-auto w-full max-w-[760px]">
        {/* EMPTY STATE — centered greeting + pill input + suggestion pills */}
        {!hasConversation && (
          <div className="flex flex-col items-stretch justify-center min-h-[calc(100vh-12rem)] pb-8 space-y-5">
            <div className="text-center select-none mb-1">
              <h1 className="text-[30px] font-medium tracking-tight text-foreground/90">
                Where should we begin?
              </h1>
            </div>

            {InputCard}

            {/* ChatGPT-style suggestion pills — small, centered row */}
            <div className="flex flex-wrap justify-center gap-2 pt-1">
              {PROMPTS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => setAsk(p.ask)}
                  title={p.ask}
                  className="inline-flex items-center h-9 px-4 rounded-full bg-foreground/[0.04] hover:bg-foreground/[0.07] text-[13px] text-foreground/75 hover:text-foreground transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* CONVERSATION — input on top, then user msg, tool calls, answer */}
        {hasConversation && (
          <div className="pt-2 space-y-5">
            {InputCard}

            {/* User message bubble */}
            <div className="flex justify-end pt-2">
              <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-foreground/[0.06] px-4 py-2.5 text-[14px] leading-relaxed">
                {result?.ask || ask || (running ? "…" : "")}
              </div>
            </div>

            {/* Live tool calls inline */}
            {liveSteps.length > 0 && (
              <div className="space-y-2">
                {liveSteps.map((step, i) => (
                  <ToolCallChip
                    key={i}
                    step={step}
                    onCompare={() => setCompareIndex(i)}
                  />
                ))}
              </div>
            )}

            {/* Composing spinner while running */}
            {running && !result && (
              <div className="flex items-center gap-2.5 text-muted-foreground text-[13px] py-2">
                <ComposingSpinner size="sm" />
                <span>Composing…</span>
              </div>
            )}

            {/* Final answer + metric strip */}
            {!running && result?.answer && (
              <ConversationAnswer result={result} onOpenTerminal={() => setTerminalOpen(true)} />
            )}

            {/* Error state */}
            {!running && error && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/[0.04] px-4 py-3">
                <p className="text-[13px] font-medium text-rose-300/90 mb-1">Couldn&apos;t run that</p>
                <p className="text-[12.5px] text-muted-foreground whitespace-pre-wrap">{error}</p>
              </div>
            )}

            {/* Per-tool full breakdown — collapsed by default */}
            {!running && result && result.steps.length > 0 && (
              <details className="group">
                <summary className="flex items-center gap-2 text-[12px] text-muted-foreground/70 hover:text-foreground cursor-pointer select-none py-1">
                  <ChevronDown className="w-3.5 h-3.5 group-open:rotate-180 transition-transform" />
                  <span>Per-tool breakdown ({result.steps.length})</span>
                </summary>
                <div className="mt-3">
                  <ResultPanel
                    result={result}
                    openSteps={openSteps}
                    toggleStep={toggleStep}
                  />
                </div>
              </details>
            )}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

/** Single tool-call chip rendered inline in the conversation flow.
 *  Click to open the compare dialog. */
function ToolCallChip({
  step,
  onCompare,
}: {
  step: Step;
  onCompare: () => void;
}) {
  const saved = step.saved_percent ?? 0;
  const cacheHit = step.cache_status === "hit";
  return (
    <button
      type="button"
      onClick={onCompare}
      className="w-full flex items-center gap-3 rounded-xl border border-border/50 bg-card/60 hover:bg-card hover:border-border transition-colors px-3.5 py-2.5 text-left"
    >
      <Sparkles className={`w-3.5 h-3.5 flex-none ${step.successful === false ? "text-rose-400" : "text-muted-foreground"}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[12px] truncate">{step.tool}</span>
          {cacheHit && (
            <span className="text-[10px] uppercase tracking-wider text-accent" style={{ color: "var(--quava-accent)" }}>
              cache hit
            </span>
          )}
          {step.tier === "degraded" && (
            <span className="text-[10px] uppercase tracking-wider text-amber-400/80">
              degraded
            </span>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground/70 mt-0.5 num">
          {(step.raw_tokens ?? 0).toLocaleString()} → {(step.sent_tokens ?? 0).toLocaleString()} tokens · {Math.round(step.elapsed_ms ?? 0).toLocaleString()} ms
        </p>
      </div>
      <span className={`text-[11px] num flex-none ${saved > 0 ? "text-foreground" : "text-muted-foreground/60"}`}>
        {saved > 0 ? `−${saved.toFixed(0)}%` : "—"}
      </span>
    </button>
  );
}

function ConversationAnswer({
  result,
  onOpenTerminal,
}: {
  result: RunResult;
  onOpenTerminal: () => void;
}) {
  const s = result.summary;
  return (
    <div className="space-y-3">
      <div className="text-[14.5px] leading-[1.65] whitespace-pre-wrap">
        {result.answer}
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground/70 pt-1 border-t border-border/30">
        <span className="num">{s.tool_calls} {s.tool_calls === 1 ? "tool" : "tools"}</span>
        <span className="text-muted-foreground/30">·</span>
        <span className="num">{s.elapsed_ms.toLocaleString()} ms</span>
        {s.saved_percent > 0 && (
          <>
            <span className="text-muted-foreground/30">·</span>
            <span className="num text-foreground/80">−{s.saved_percent.toFixed(1)}% smaller</span>
          </>
        )}
        {(s.cost_saved_usd ?? 0) > 0 && (
          <>
            <span className="text-muted-foreground/30">·</span>
            <span className="num text-foreground/80">${(s.cost_saved_usd).toFixed(4)} saved</span>
          </>
        )}
        {result.served_from_cache && (
          <>
            <span className="text-muted-foreground/30">·</span>
            <span className="text-foreground/80">cached · $0</span>
          </>
        )}
        <button
          type="button"
          onClick={onOpenTerminal}
          className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
        >
          view tool calls →
        </button>
      </div>
    </div>
  );
}

/** Compact mode selector — opens a popover instead of a 6-button bar. */
// ChatGPT-style mode chip: subtle text "{label} ⌄" that opens a small
// popover anchored to the button.
function ModePill({
  modes,
  value,
  onChange,
  disabled,
}: {
  modes: { value: EffortMode; label: string; detail: string }[];
  value: EffortMode;
  onChange: (v: EffortMode) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selected = modes.find((m) => m.value === value) ?? modes[3];
  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 h-8 px-3 rounded-full text-[13px] font-medium text-foreground/85 hover:bg-foreground/[0.05] hover:text-foreground transition-colors disabled:opacity-50"
        title="Compression mode"
      >
        {selected.label}
        <ChevronDown className="w-3.5 h-3.5 text-foreground/60" />
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div
            className="absolute bottom-full mb-2 right-0 z-50 w-[220px] rounded-xl shadow-2xl overflow-hidden py-1.5 border border-border/70"
            style={{ backgroundColor: "var(--quava-surface-container-high, #161616)" }}
          >
            <p className="px-3 pt-1 pb-1.5 text-[10.5px] uppercase tracking-wider text-muted-foreground/70">
              Compression mode
            </p>
            {modes.map((m) => {
              const sel = m.value === value;
              return (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => {
                    onChange(m.value);
                    setOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 transition-colors ${
                    sel ? "bg-foreground/[0.06]" : "hover:bg-foreground/[0.04]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px]">{m.label}</span>
                    {sel && <Check className="w-3.5 h-3.5 text-foreground" />}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{m.detail}</p>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// Local alias so the terminal sees the slimmer step shape it actually
// reads. The full Step interface above has many more optional fields.
type RunTerminalStepData = import("@/components/RunTerminal").RunTerminalStep;

function ResultPanel({
  result,
  openSteps,
  toggleStep,
}: {
  result: RunResult;
  openSteps: Set<number>;
  toggleStep: (i: number) => void;
}) {
  const s = result.summary;
  return (
    <div className="space-y-3">
      <Card className="border-primary/40">
        <CardContent className="pt-5 pb-5 space-y-4">
          <div className="flex items-center justify-center gap-2 flex-wrap text-center">
            <span className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
              <Check className="w-3 h-3" />
            </span>
            <p className="text-sm font-medium">
              Done. {s.tool_calls} tool call{s.tool_calls === 1 ? "" : "s"} in{" "}
              {s.elapsed_ms} ms.
            </p>
            {!result.served_from_cache && (s.composio_calls_avoided ?? 0) > 0 && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-primary/40 bg-primary/10 text-[10px] font-mono text-primary"
                title="Tool-call cache hit — Composio was not billed for these calls"
              >
                <span className="lime-dot" />
                {s.composio_calls_avoided} composio call
                {s.composio_calls_avoided === 1 ? "" : "s"} avoided · ~$
                {(s.composio_cost_avoided_usd ?? 0).toFixed(4)} saved on Composio
              </span>
            )}
          </div>

          <div className="mx-auto grid w-full max-w-2xl grid-cols-3 gap-4 pt-1 text-center">
            <Metric
              label="Raw"
              value={s.raw_tokens.toLocaleString()}
              sublabel="tokens from tools"
              tone="raw"
            />
            <Metric
              label="Sent"
              value={s.sent_tokens.toLocaleString()}
              sublabel="tokens to LLM"
              tone="sent"
            />
            <Metric
              label="Saved"
              value={`${s.saved_percent}%`}
              sublabel={`$${s.cost_saved_usd.toFixed(4)} cheaper`}
              tone="saved"
            />
          </div>
        </CardContent>
      </Card>

      {result.steps.map((step, i) => (
        <StepCard
          key={i}
          step={step}
          open={openSteps.has(i)}
          onToggle={() => toggleStep(i)}
        />
      ))}

      {result.cost && <CostPanel cost={result.cost} model={result.model} />}

      {result.answer && (
        <TerminalBlock
          title="quava · agent"
          lines={agentReplyTerminalLines(result.answer)}
          animate={false}
        />
      )}
    </div>
  );
}

function agentReplyTerminalLines(answer: string): TerminalLine[] {
  const cleaned = answer
    .replace(/\*\*/g, "")
    .replace(/&mdash;/g, "—")
    .trim();

  const lines = cleaned.split(/\r?\n/);
  return [
    { kind: "command", text: "agent reply" },
    ...lines.map((line) => ({
      kind: line.trim() ? "output" : "output",
      text: line,
    } satisfies TerminalLine)),
  ];
}

function CostPanel({ cost, model }: { cost: CostBlock; model: string }) {
  const fmtUsd = (v: number): string =>
    v < 0.01 ? `$${v.toFixed(6)}` : `$${v.toFixed(4)}`;
  const costIncreasePercent = Math.round(
    (cost.saved_usd / Math.max(cost.actual_usd, 1e-9)) * 100
  );

  return (
    <Card>
      <CardContent className="pt-4 pb-4 space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Per-model cost
            </p>
            <p className="text-[13px] font-medium mt-0.5">
              <span className="font-mono text-foreground">{model}</span>
              <span className="text-muted-foreground/60"> · what you actually paid</span>
            </p>
          </div>
          <Badge variant="default" className="text-[10px]">
            {fmtUsd(cost.saved_usd)} saved
          </Badge>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <CostTile
            label="You spent"
            primary
            value={fmtUsd(cost.actual_usd)}
            sublabel={`${cost.input_tokens.toLocaleString()} in · ${cost.output_tokens.toLocaleString()} out`}
          />
          <CostTile
            label="Without Quava"
            value={fmtUsd(cost.counterfactual_usd)}
            sublabel={`${cost.raw_input_tokens.toLocaleString()} in · uncached`}
            strike
          />
          <CostTile
            label="More without Quava"
            value={`+${costIncreasePercent}%`}
            sublabel={
              cost.saved_usd > 0
                ? `${fmtUsd(cost.saved_usd)} extra`
                : "no extra cost"
            }
          />
        </div>

        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Anthropic billed{" "}
          <span className="num text-foreground">{fmtUsd(cost.actual_usd)}</span> for
          this run. Without Quava compressing the {cost.raw_input_tokens.toLocaleString()}{" "}
          raw tool tokens, the same {cost.output_tokens.toLocaleString()}-token answer
          would have cost{" "}
          <span className="num text-foreground">{fmtUsd(cost.counterfactual_usd)}</span>{" "}
          &mdash; ~{costIncreasePercent}%
          more.
        </p>
      </CardContent>
    </Card>
  );
}

function CostTile({
  label,
  value,
  sublabel,
  primary,
  strike,
}: {
  label: string;
  value: string;
  sublabel?: string;
  primary?: boolean;
  strike?: boolean;
}) {
  return (
    <div className="rounded-md border border-border/40 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p
        className={`text-[15px] font-semibold metric-value ${
          primary ? "text-primary" : strike ? "text-muted-foreground line-through" : ""
        }`}
      >
        {value}
      </p>
      {sublabel && (
        <p className="text-[10px] text-muted-foreground/80 metric-value mt-0.5">
          {sublabel}
        </p>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  sublabel,
  tone,
}: {
  label: string;
  value: string;
  sublabel?: string;
  tone: "raw" | "sent" | "saved";
}) {
  const valueClass = {
    raw: "text-rose-300",
    sent: "text-sky-300",
    saved: "text-emerald-300",
  }[tone];

  return (
    <div className="text-center">
      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className={`text-xl font-semibold metric-value ${valueClass}`}>
        {value}
      </p>
      {sublabel && (
        <p className="text-[10px] text-muted-foreground metric-value">{sublabel}</p>
      )}
    </div>
  );
}

function StepCard({
  step,
  open,
  onToggle,
}: {
  step: Step;
  open: boolean;
  onToggle: () => void;
}) {
  const args = step.arguments ?? {};
  const argsKeys = Object.keys(args);
  const successful = step.successful !== false;
  const classifierKeeps = step.classifier_keeps ?? [];
  const omittedFields = step.omitted_fields ?? step.breakdown?.all_api_fields_removed ?? [];
  const policyPromotions = step.policy_promotions ?? [];
  const savedPercent = step.saved_percent ?? roundSavedPercent(step);
  const strategy = step.strategy ?? step.breakdown?.strategy ?? "balanced";
  return (
    <Card className={successful ? "" : "border-rose-500/40"}>
      <CardContent className="pt-4 pb-4 space-y-3">
        <button
          type="button"
          onClick={onToggle}
          className="w-full flex items-center justify-between gap-3 text-left"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="font-mono text-[11px] text-foreground truncate">
              {step.tool}
            </span>
            {!successful && (
              <Badge variant="destructive" className="text-[10px]">error</Badge>
            )}
            {step.cache_status === "hit" && (
              <span
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-primary/30 bg-primary/10 text-[9px] font-mono text-primary"
                title={`Tool-call cache hit · age ${step.cache_age_seconds ?? 0}s · Composio not billed`}
              >
                <span className="lime-dot" />
                composio skipped · ${step.composio_cost_avoided_usd?.toFixed(4) ?? "0.0000"}
              </span>
            )}
            {step.cache_status === "blocked_write" && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-[9px] font-mono text-amber-300"
                    title="Read-only mode blocked this write tool before Composio saw it">
                read-only · blocked
              </span>
            )}
            {step.tier && step.tier !== "full" && (
              <span
                className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[9px] font-mono uppercase tracking-wider ${
                  step.tier === "degraded"
                    ? "border-amber-500/30 bg-amber-500/5 text-amber-300"
                    : "border-rose-500/30 bg-rose-500/5 text-rose-300"
                }`}
                title="3-tier degradation marker · ported from rtk"
              >
                {step.tier}
              </span>
            )}
            {step.classifier_used && classifierKeeps.length > 0 && (
              <span
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-primary/30 bg-primary/5 text-[9px] font-mono text-primary"
                title={`Small-LLM classifier rescued: ${classifierKeeps.join(", ")}`}
              >
                <span className="lime-dot" />
                brain · +{classifierKeeps.length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-none">
            <span className="text-[11px] metric-value text-muted-foreground">
              <span className="text-foreground">{step.sent_tokens.toLocaleString()}</span>
              <span className="mx-1">/</span>
              {step.raw_tokens.toLocaleString()}
            </span>
            <Badge variant="default" className="text-[10px]">
              {savedPercent}% saved
            </Badge>
            {open ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                  : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
          </div>
        </button>

        {!successful && step.error && (
          <p className="text-[11px] text-rose-300 font-mono">{step.error}</p>
        )}

        {open && successful && (
          <div className="space-y-3 pt-1 border-t border-border/40">
            <div className="grid grid-cols-3 gap-2 pt-3">
              <KV label="Strategy" value={strategy} />
              <KV label="Mode" value={step.effort_mode ?? "medium"} />
              <KV label="Latency" value={typeof step.elapsed_ms === "number" ? `${Math.round(step.elapsed_ms)} ms` : "not tracked"} />
            </div>

            {argsKeys.length > 0 && (
              <Collapsible label={`Arguments · ${argsKeys.length}`}>
                <pre className="text-[11px] font-mono bg-muted/40 p-2 rounded overflow-auto">
                  {JSON.stringify(args, null, 2)}
                </pre>
              </Collapsible>
            )}

            {omittedFields.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-1.5">
                  Quava dropped {omittedFields.length} bookkeeping field
                  {omittedFields.length === 1 ? "" : "s"}
                </p>
                <div className="flex flex-wrap gap-1">
                  {omittedFields.slice(0, 18).map((f) => (
                    <span
                      key={f}
                      className="inline-flex items-center px-1.5 py-0.5 rounded border border-rose-500/30 bg-rose-500/5 text-[10px] font-mono text-rose-300"
                    >
                      {f}
                    </span>
                  ))}
                  {omittedFields.length > 18 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{omittedFields.length - 18} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {policyPromotions.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-1.5">
                  Quava rescued {policyPromotions.length} field
                  {policyPromotions.length === 1 ? "" : "s"} the ask asked for
                </p>
                <div className="flex flex-wrap gap-1">
                  {policyPromotions.slice(0, 12).map((p, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-primary/30 bg-primary/10 text-[10px] font-mono text-primary"
                    >
                      {p.name}
                      <span className="text-primary/60">· {p.reason}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}
      </CardContent>
    </Card>
  );
}

function roundSavedPercent(step: Step): number {
  if (!step.raw_tokens) return 0;
  return Math.round((step.saved_tokens / step.raw_tokens) * 1000) / 10;
}

function KV({ label, value, primary }: { label: string; value: string; primary?: boolean }) {
  return (
    <div className="rounded-md border border-border/40 px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className={`text-[12px] font-mono metric-value ${primary ? "text-primary" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function Collapsible({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-1.5">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground flex items-center gap-1"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {label}
      </button>
      {open && children}
    </div>
  );
}

