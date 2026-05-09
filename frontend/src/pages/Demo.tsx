import { useState } from "react";
import { apiPost, describeApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowUpRight, Check, ChevronDown, ChevronUp } from "lucide-react";
import { ComposingSpinner } from "@/components/ComposingSpinner";

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
  iterations: number;
  stopped_reason: string;
  error: string | null;
  summary: Summary;
  cost?: CostBlock | null;
  steps: Step[];
}

interface RunHistoryEntry {
  ts: number;
  ask: string;
  answer: string;
  model: string;
  summary: Summary;
  steps: Step[];
}

const HISTORY_KEY = "aperture.runs.v1";
const HISTORY_LIMIT = 30;

function appendRunToHistory(result: RunResult): void {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    const list: RunHistoryEntry[] = raw ? JSON.parse(raw) : [];
    list.unshift({
      ts: Date.now(),
      ask: result.ask,
      answer: result.answer,
      model: result.model,
      summary: result.summary,
      steps: result.steps,
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
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openSteps, setOpenSteps] = useState<Set<number>>(new Set());

  const submit = async (): Promise<void> => {
    const trimmed = ask.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setResult(null);
    setError(null);
    setOpenSteps(new Set());
    try {
      const r = await apiPost<RunResult>("/api/demo/run", { ask: trimmed });
      if (!r || !r.summary) {
        setError("Backend returned an empty response.");
      } else if (r.error) {
        setError(r.error);
        setResult(r);
        appendRunToHistory(r);
      } else {
        setResult(r);
        appendRunToHistory(r);
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
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
    <div className="max-w-3xl mx-auto py-8 space-y-6">
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
          <div className="flex items-center gap-2 flex-wrap">
            <span className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
              <Check className="w-3 h-3" />
            </span>
            <p className="text-sm font-medium">
              Done. {s.tool_calls} tool call{s.tool_calls === 1 ? "" : "s"} in{" "}
              {s.elapsed_ms} ms.
            </p>
          </div>

          {result.answer && (
            <div className="rounded-md border border-border/60 bg-muted/20 p-3">
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-1">
                Agent reply
              </p>
              <p className="text-[13px] whitespace-pre-wrap leading-relaxed">
                {result.answer}
              </p>
            </div>
          )}

          <div className="grid grid-cols-3 gap-4 pt-1">
            <Metric label="Raw" value={s.raw_tokens.toLocaleString()} sublabel="tokens from tools" />
            <Metric label="Sent" value={s.sent_tokens.toLocaleString()} sublabel="tokens to LLM" />
            <Metric
              label="Saved"
              value={`${s.saved_percent}%`}
              sublabel={`$${s.cost_saved_usd.toFixed(4)} cheaper`}
              primary
            />
          </div>
        </CardContent>
      </Card>

      {result.cost && <CostPanel cost={result.cost} model={result.model} />}

      {result.steps.map((step, i) => (
        <StepCard
          key={i}
          step={step}
          open={openSteps.has(i)}
          onToggle={() => toggleStep(i)}
        />
      ))}
    </div>
  );
}

function CostPanel({ cost, model }: { cost: CostBlock; model: string }) {
  const fmtUsd = (v: number): string =>
    v < 0.01 ? `$${v.toFixed(6)}` : `$${v.toFixed(4)}`;
  const cacheTokens = cost.cache_read_tokens + cost.cache_write_tokens;
  const totalIn = cost.input_tokens + cacheTokens;

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
            label="Cache hits"
            value={`${cost.cache_hit_rate}%`}
            sublabel={
              cacheTokens > 0
                ? `${cost.cache_read_tokens.toLocaleString()}/${totalIn.toLocaleString()} tok`
                : "first run · cache warming"
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
          &mdash; ~{Math.round((cost.saved_usd / Math.max(cost.counterfactual_usd, 1e-9)) * 100)}%
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
  primary,
}: {
  label: string;
  value: string;
  sublabel?: string;
  primary?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className={`text-xl font-semibold metric-value ${primary ? "text-primary" : ""}`}>
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
  const llmFormat = step.llm_format ?? step.breakdown?.llm_format ?? "json";
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
            {step.ultra_summary && (
              <div className="rounded-md border border-primary/30 bg-primary/[0.04] px-2.5 py-2">
                <p className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground mb-0.5">
                  Ultra-summary <span className="text-muted-foreground/60">(rtk-style headline · top of payload)</span>
                </p>
                <p className="text-[12px] font-mono text-primary leading-relaxed">
                  ≡ {step.ultra_summary}
                </p>
              </div>
            )}
            <div className="grid grid-cols-3 gap-2 pt-3">
              <KV label="Strategy" value={strategy} />
              <KV label="Encoding" value={llmFormat} />
              <KV label="Latency" value={typeof step.elapsed_ms === "number" ? `${Math.round(step.elapsed_ms)} ms` : "not tracked"} />
              <KV label="Raw bytes" value={typeof step.raw_bytes === "number" ? step.raw_bytes.toLocaleString() : "not tracked"} />
              <KV label="Sent bytes" value={typeof step.sent_bytes === "number" ? step.sent_bytes.toLocaleString() : "not tracked"} />
              <KV label="Saved" value={`${step.saved_tokens.toLocaleString()} tok`} primary />
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

            <div className="grid grid-cols-2 gap-2">
              <PreviewPane
                label="Composio returned"
                tokens={step.raw_tokens}
                content={step.raw_preview ?? ""}
                tone="muted"
              />
              <PreviewPane
                label="What we sent the model"
                tokens={step.sent_tokens}
                content={step.compressed_preview ?? step.breakdown?.remaining_sentence ?? ""}
                tone="primary"
              />
            </div>
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

function PreviewPane({
  label,
  tokens,
  content,
  tone,
}: {
  label: string;
  tokens: number;
  content: string;
  tone: "muted" | "primary";
}) {
  return (
    <div
      className={`rounded-md border ${
        tone === "primary" ? "border-primary/40 bg-primary/5" : "border-border/60 bg-muted/20"
      } overflow-hidden flex flex-col`}
    >
      <div className="px-2.5 py-1.5 flex items-center justify-between border-b border-border/40">
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
        <span className="text-[10px] metric-value text-muted-foreground">
          {tokens.toLocaleString()} tok
        </span>
      </div>
      <pre className="text-[10px] font-mono leading-relaxed p-2 overflow-auto whitespace-pre-wrap min-h-[100px] max-h-[220px]">
        {content || "(empty)"}
      </pre>
    </div>
  );
}

