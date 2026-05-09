import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowUpRight, Check, ChevronDown, ChevronUp } from "lucide-react";

interface Step {
  tool: string;
  raw_tokens: number;
  sent_tokens: number;
  saved_tokens: number;
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

interface RunResult {
  ask: string;
  summary: Summary;
  steps: Step[];
}

const PROMPTS = [
  "Look up the composio repo — stars, open issues, recent PRs",
  "Find all OAuth bugs and tell me who's assigned",
  "Summarize 500 Notion pages, 200 Linear issues, and 1000 Supabase users",
  "Scan my inbox for anything urgent from this week",
];

export default function Demo() {
  const [ask, setAsk] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [showSteps, setShowSteps] = useState(false);

  const submit = async () => {
    const trimmed = ask.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setResult(null);
    setShowSteps(false);
    const r: RunResult = await apiPost("/api/demo/run", { ask: trimmed });
    setResult(r);
    setRunning(false);
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
  };

  return (
    <div className="max-w-2xl mx-auto py-12 space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          Aperture
        </p>
        <h1 className="text-2xl font-semibold tracking-tight mt-1">
          What do you want your agent to do?
        </h1>
      </div>

      <div className="rounded-xl border border-border bg-card p-4 space-y-3">
        <textarea
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          onKeyDown={onKey}
          placeholder="Describe a task in plain English — e.g. find open OAuth bugs and tell me who's assigned"
          rows={3}
          className="w-full resize-none bg-transparent text-[14px] outline-none placeholder:text-muted-foreground/70"
          autoFocus
        />
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-1.5">
            {PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setAsk(p)}
                className="text-[11px] px-2 py-1 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
              >
                {p.length > 40 ? p.slice(0, 40) + "…" : p}
              </button>
            ))}
          </div>
          <Button
            onClick={submit}
            disabled={!ask.trim() || running}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {running ? "Running…" : (
              <>Run <ArrowUpRight className="w-4 h-4 ml-1" /></>
            )}
          </Button>
        </div>
      </div>

      {running && <RunningSpinner />}

      {!running && result && <ResultPopup result={result} showSteps={showSteps} setShowSteps={setShowSteps} />}
    </div>
  );
}

function RunningSpinner() {
  return (
    <Card>
      <CardContent className="pt-5 pb-5 flex items-center gap-3">
        <span className="text-primary text-[16px] aperture-pulse">✽</span>
        <span className="text-sm text-muted-foreground">working…</span>
      </CardContent>
    </Card>
  );
}

function ResultPopup({
  result,
  showSteps,
  setShowSteps,
}: {
  result: RunResult;
  showSteps: boolean;
  setShowSteps: (v: boolean) => void;
}) {
  const s = result.summary;
  return (
    <div className="space-y-3">
      <Card className="border-primary/40">
        <CardContent className="pt-5 pb-5 space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
              <Check className="w-3 h-3" />
            </span>
            <p className="text-sm font-medium">
              Done. {s.tool_calls} tool call{s.tool_calls === 1 ? "" : "s"} in {s.elapsed_ms} ms.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4 pt-1">
            <Metric label="Raw" value={s.raw_tokens.toLocaleString()} sublabel="tokens" />
            <Metric label="Sent" value={s.sent_tokens.toLocaleString()} sublabel="tokens" />
            <Metric label="Saved" value={`${s.saved_percent}%`} sublabel={`$${s.cost_saved_usd.toFixed(4)} cheaper`} primary />
          </div>

          <button
            type="button"
            onClick={() => setShowSteps(!showSteps)}
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            {showSteps ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showSteps ? "Hide" : "Show"} per-tool breakdown
          </button>
        </CardContent>
      </Card>

      {showSteps && <ToolCallChart steps={result.steps} />}
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
      <p className={`text-xl font-semibold metric-value ${primary ? "text-primary" : ""}`}>{value}</p>
      {sublabel && <p className="text-[10px] text-muted-foreground metric-value">{sublabel}</p>}
    </div>
  );
}

function ToolCallChart({ steps }: { steps: Step[] }) {
  const max = Math.max(...steps.map((s) => s.raw_tokens), 1);
  return (
    <Card>
      <CardContent className="pt-5 pb-5 space-y-3">
        <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
          Per-tool · raw vs sent
        </p>
        <div className="space-y-2.5">
          {steps.map((step, i) => {
            const sentPct = (step.sent_tokens / max) * 100;
            const savedPct = (step.saved_tokens / max) * 100;
            return (
              <div key={i} className="space-y-1">
                <div className="flex items-baseline justify-between text-[11px]">
                  <span className="font-mono text-foreground/85">{step.tool}</span>
                  <span className="metric-value text-muted-foreground">
                    <span className="text-foreground">{step.sent_tokens.toLocaleString()}</span>
                    <span className="mx-1">/</span>
                    {step.raw_tokens.toLocaleString()}
                  </span>
                </div>
                <div className="relative h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 bg-primary"
                    style={{ width: `${sentPct}%` }}
                  />
                  <div
                    className="absolute inset-y-0 bg-foreground/20"
                    style={{ left: `${sentPct}%`, width: `${savedPct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3 pt-1 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-primary" /> sent
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-foreground/20" /> saved
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// Re-export with a type — components expect Badge but we don't actually use it
export { Badge };
