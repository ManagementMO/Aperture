import { useEffect, useState } from "react";
import { apiGet, apiPost, describeApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowUpRight, Check, ChevronDown, ChevronUp } from "lucide-react";
import { ComposingSpinner } from "@/components/ComposingSpinner";
import { TerminalBlock, type TerminalLine } from "@/components/TerminalBlock";

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
  const [toolCache, setToolCache] = useState<ToolCacheStats | null>(null);
  const [toolCacheSnapshotMs, setToolCacheSnapshotMs] = useState(Date.now());
  const [nowMs, setNowMs] = useState(Date.now());
  const [cacheError, setCacheError] = useState<string | null>(null);
  const selectedMode =
    MODES.find((mode) => mode.value === effortMode) ??
    MODES.find((mode) => mode.value === "medium")!;

  const applyToolCache = (stats: ToolCacheStats): void => {
    setToolCache(stats);
    setToolCacheSnapshotMs(Date.now());
  };

  const refreshToolCache = async (): Promise<void> => {
    try {
      const stats = await apiGet<ToolCacheStats>("/api/cache/tools");
      applyToolCache(stats);
      setCacheError(null);
    } catch (err) {
      setCacheError(describeApiError(err));
    }
  };

  useEffect(() => {
    const initializeDemoCache = async (): Promise<void> => {
      await refreshToolCache();
    };

    void initializeDemoCache();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const submit = async (): Promise<void> => {
    const trimmed = ask.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setResult(null);
    setError(null);
    setOpenSteps(new Set());
    let usedRunCacheSnapshot = false;
    try {
      const r = await apiPost<RunResult>("/api/demo/run", {
        ask: trimmed,
        effort_mode: effortMode,
      });
      if (!r || !r.summary) {
        setError("Backend returned an empty response.");
      } else if (r.error) {
        setError(r.error);
        setResult(r);
        if (r.cache) {
          applyToolCache(r.cache);
          usedRunCacheSnapshot = true;
        }
        appendRunToHistory(r);
      } else {
        setResult(r);
        if (r.cache) {
          applyToolCache(r.cache);
          usedRunCacheSnapshot = true;
        }
        appendRunToHistory(r);
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      if (!usedRunCacheSnapshot) void refreshToolCache();
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

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8.5rem)] w-full max-w-3xl flex-col justify-center py-8 space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          Aperture
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">
          What do you want your agent to do?
        </h1>
        <p className="text-sm text-muted-foreground mt-2">
          Aperture stays between your agent and its tools. Type an ask &mdash;
          a real agent picks Composio tools, runs them, Aperture compresses
          each response before the model reads it.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card/80 backdrop-blur-sm p-4 space-y-3">
        <textarea
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask anything that needs a real tool. ⌘+Enter to run."
          rows={3}
          className="w-full resize-none bg-transparent text-[14px] outline-none placeholder:text-muted-foreground/60"
          autoFocus
        />
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5">
            {PROMPTS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setAsk(p.ask)}
                className="text-[11px] px-2 py-1 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
              >
                {p.label}
              </button>
            ))}
          </div>
          <Button
            onClick={() => void submit()}
            disabled={!ask.trim() || running}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {running ? <ComposingSpinner label="Running" /> : (
              <>Run <ArrowUpRight className="w-4 h-4 ml-1" /></>
            )}
          </Button>
        </div>
        <div className="border-t border-border/50 pt-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Mode
            </p>
            <span className="inline-flex items-center gap-1.5 rounded border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-mono uppercase text-primary">
              <Check className="h-3 w-3" />
              {selectedMode.label}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
            {MODES.map((mode) => {
              const selected = effortMode === mode.value;
              return (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() => setEffortMode(mode.value)}
                  disabled={running}
                  className={`rounded-md border px-2 py-2 text-left transition-colors ${
                    selected
                      ? "border-primary bg-primary/15 text-foreground shadow-[0_0_0_1px_hsl(var(--primary)/0.35)]"
                      : "border-border/70 text-muted-foreground hover:border-primary/50 hover:text-foreground"
                  } disabled:opacity-60`}
                  aria-pressed={selected}
                >
                  <span className="flex items-center justify-between gap-2 text-[12px] font-medium">
                    {mode.label}
                    {selected && <Check className="h-3 w-3 text-primary" />}
                  </span>
                  <span className="block text-[9px] leading-tight text-muted-foreground mt-0.5">
                    {mode.detail}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {running && (
        <Card>
          <CardContent className="pt-5 pb-5">
            <ComposingSpinner size="md" label="Agent is composing" />
          </CardContent>
        </Card>
      )}

      {!running && error && (
        <Card className="border-rose-500/40">
          <CardContent className="pt-5 pb-5 space-y-1">
            <p className="text-sm font-medium text-rose-400">Couldn&apos;t run that.</p>
            <p className="text-[12px] text-muted-foreground whitespace-pre-wrap">{error}</p>
          </CardContent>
        </Card>
      )}

      {!running && result && result.summary && (
        <ResultPanel
          result={result}
          openSteps={openSteps}
          toggleStep={toggleStep}
        />
      )}

      <ToolCachePanel
        result={result}
        stats={toolCache}
        snapshotMs={toolCacheSnapshotMs}
        nowMs={nowMs}
        error={cacheError}
      />
    </div>
  );
}

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
          title="aperture · agent"
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

function ToolCachePanel({
  result,
  stats,
  snapshotMs,
  nowMs,
  error,
}: {
  result: RunResult | null;
  stats: ToolCacheStats | null;
  snapshotMs: number;
  nowMs: number;
  error: string | null;
}) {
  const toolItems = stats?.items ?? [];
  const resultItems: {
    ask: string;
    model: string;
    effort_mode?: EffortMode;
    tool_calls?: number;
    ttl_remaining_seconds?: number | null;
  }[] = [];
  const activeToolItems = toolItems.filter(
    (item) => cacheSecondsRemaining(item.ttl_remaining_seconds, snapshotMs, nowMs) > 0
  );
  const empty = activeToolItems.length === 0;
  const visibleCount = stats ? activeToolItems.length : null;

  return (
    <div className="space-y-3">
      {result?.served_from_cache && (
        <div className="flex items-center justify-center gap-2 rounded-md border border-primary/40 bg-primary/10 px-3 py-2 text-[12px] font-mono text-primary">
          <span className="lime-dot" />
          <span>this run was served from cache · 0 ms · $0.000000 spent</span>
        </div>
      )}

      <Card>
        <CardContent className="pt-4 pb-4 space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                Tool result cache
              </p>
              <p className="text-[12px] text-muted-foreground mt-0.5">
                Read-only tool results available for repeat calls.
              </p>
            </div>
            <Badge variant="outline" className="text-[10px]">
              {visibleCount !== null ? `${visibleCount} cached` : "loading"}
            </Badge>
          </div>

          {error && (
            <p className="text-[11px] text-rose-300">{error}</p>
          )}

          {!error && empty && (
            <p className="text-[11px] text-muted-foreground">
              No cached tool results yet.
            </p>
          )}

          {resultItems.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                Run result cache
              </p>
              {resultItems.map((item) => (
                <div
                  key={`${item.model}-${item.effort_mode ?? "mode"}-${item.ask}`}
                  className="flex items-center justify-between gap-3 rounded-md border border-primary/30 bg-primary/5 px-2.5 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[11px] text-foreground">
                      {item.ask}
                    </p>
                    <p className="truncate text-[10px] text-muted-foreground">
                      {item.model} · {item.effort_mode ?? "medium"} · {item.tool_calls ?? 0} tool calls skipped on replay
                    </p>
                  </div>
                  <div className="flex-none text-right">
                    <p className="text-[10px] font-mono text-primary">
                      {formatSeconds(item.ttl_remaining_seconds)} left
                    </p>
                    <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground/70">
                      full run
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeToolItems.length > 0 && (
            <div className="space-y-1.5">
              {activeToolItems.map((item) => (
                <div
                  key={`${item.cache_key_hash ?? item.tool}-${item.age_seconds ?? 0}`}
                  className="flex items-center justify-between gap-3 rounded-md border border-border/50 px-2.5 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[11px] text-foreground">
                      {item.tool}
                    </p>
                    <p className="truncate text-[10px] text-muted-foreground">
                      {formatCacheArguments(item.arguments)}
                    </p>
                  </div>
                  <div className="flex-none text-right">
                    <p className="text-[10px] font-mono text-muted-foreground">
                      {formatSeconds(item.ttl_remaining_seconds, snapshotMs, nowMs)} left
                    </p>
                    <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground/70">
                      {item.cache_scope ?? "cache"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function formatCacheArguments(args?: Record<string, unknown>): string {
  if (!args || Object.keys(args).length === 0) return "no arguments";
  return Object.entries(args)
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" · ");
}

function cacheSecondsRemaining(
  value?: number | null,
  snapshotMs?: number,
  nowMs?: number
): number {
  if (typeof value !== "number") return Number.POSITIVE_INFINITY;
  const elapsedSeconds =
    typeof snapshotMs === "number" && typeof nowMs === "number"
      ? Math.max(0, (nowMs - snapshotMs) / 1000)
      : 0;
  return Math.max(0, value - elapsedSeconds);
}

function formatSeconds(value?: number | null, snapshotMs?: number, nowMs?: number): string {
  if (typeof value !== "number") return "unknown";
  const remaining = cacheSecondsRemaining(value, snapshotMs, nowMs);
  if (remaining < 60) return `${Math.ceil(remaining)}s`;
  return `${Math.floor(remaining / 60)}m ${Math.ceil(remaining % 60)}s`;
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
            label="Without Aperture"
            value={fmtUsd(cost.counterfactual_usd)}
            sublabel={`${cost.raw_input_tokens.toLocaleString()} in · uncached`}
            strike
          />
          <CostTile
            label="More without Aperture"
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
          this run. Without Aperture compressing the {cost.raw_input_tokens.toLocaleString()}{" "}
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
                  Aperture dropped {omittedFields.length} bookkeeping field
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
                  Aperture rescued {policyPromotions.length} field
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

