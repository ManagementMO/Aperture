import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
// `Button` kept for the Trash2 ghost button below.
void Button;
import {
  ArrowUpRight,
  Database,
  FileText,
  GitBranch,
  ListTodo,
  Mail,
  MessageSquare,
  Sheet,
  Trash2,
} from "lucide-react";

const HISTORY_KEY = "aperture.runs.v1";

interface Step {
  tool: string;
  raw_tokens: number;
  sent_tokens: number;
  saved_tokens: number;
}

interface MatchedIntent {
  id: string;
  label: string;
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

interface RunHistoryEntry {
  ts: number;
  ask: string;
  matched_intent?: MatchedIntent;
  summary: Summary;
  steps: Step[];
}

const SOURCE_FOR_TOOL: Record<string, { label: string; icon: typeof GitBranch }> = {
  github: { label: "GitHub", icon: GitBranch },
  gmail: { label: "Gmail", icon: Mail },
  slack: { label: "Slack", icon: MessageSquare },
  notion: { label: "Notion", icon: FileText },
  linear: { label: "Linear", icon: ListTodo },
  supabase: { label: "Supabase", icon: Database },
  googlesheets: { label: "Sheets", icon: Sheet },
};

function lookupSource(toolLabel: string): { label: string; icon: typeof GitBranch } {
  const lowered = toolLabel.toLowerCase();
  for (const key in SOURCE_FOR_TOOL) {
    if (lowered.includes(key)) return SOURCE_FOR_TOOL[key];
  }
  return { label: "Tool", icon: GitBranch };
}

function loadHistory(): RunHistoryEntry[] {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function fmtRelative(ts: number): string {
  const delta = Math.floor((Date.now() - ts) / 1000);
  if (delta < 5) return "just now";
  if (delta < 60) return `${delta}s ago`;
  const m = Math.floor(delta / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function TokenWaterfall() {
  const [history, setHistory] = useState<RunHistoryEntry[]>(loadHistory);

  useEffect(() => {
    const handler = () => setHistory(loadHistory());
    window.addEventListener("aperture:run", handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener("aperture:run", handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  const clear = () => {
    window.localStorage.removeItem(HISTORY_KEY);
    setHistory([]);
  };

  const totalRaw = history.reduce((s, r) => s + r.summary.raw_tokens, 0);
  const totalSent = history.reduce((s, r) => s + r.summary.sent_tokens, 0);
  const totalCalls = history.reduce((s, r) => s + r.summary.tool_calls, 0);
  const totalSaved = totalRaw - totalSent;
  const overallPct = totalRaw > 0 ? (totalSaved / totalRaw) * 100 : 0;

  return (
    <div className="space-y-7">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Token waterfall
        </p>
        <div className="flex items-baseline justify-between gap-3 mt-1">
          <h1 className="text-3xl font-semibold tracking-tight">Session log</h1>
          {history.length > 0 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={clear}
              className="text-[11px] text-muted-foreground hover:text-foreground"
            >
              <Trash2 className="w-3 h-3 mr-1" /> Clear
            </Button>
          )}
        </div>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
          Every Demo run lands here. Tool calls accumulate across the session
          so you can see what the agent actually touched and what Aperture
          shrank along the way.
        </p>
      </div>

      {history.length === 0 ? (
        <Card>
          <CardContent className="pt-8 pb-8 flex flex-col items-center text-center gap-3">
            <div className="w-10 h-10 rounded-full border border-border flex items-center justify-center">
              <ArrowUpRight className="w-4 h-4 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">No runs yet.</p>
            <p className="text-[12px] text-muted-foreground max-w-md">
              Head to the Demo, type a task, and hit Run. Every tool call
              your run touches will accumulate here automatically.
            </p>
            <Link
              to="/"
              className="mt-1 inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Go to Run <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            <Stat label="Runs" value={history.length} sub="this session" />
            <Stat label="Tool calls" value={totalCalls} sub="across all runs" />
            <Stat label="Sent" value={totalSent} sub={`of ${totalRaw.toLocaleString()} raw`} />
            <Stat
              label="Saved"
              value={Math.round(overallPct * 10) / 10}
              suffix="%"
              sub={`${totalSaved.toLocaleString()} tokens`}
              primary
            />
          </div>

          <div className="space-y-3">
            {history.map((run) => (
              <RunCard key={run.ts} run={run} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  suffix,
  primary,
}: {
  label: string;
  value: number;
  sub?: string;
  suffix?: string;
  primary?: boolean;
}) {
  return (
    <Card className={primary ? "border-primary/30" : ""}>
      <CardContent className="pt-5 space-y-1">
        <p
          className={`text-[11px] uppercase tracking-[0.14em] ${
            primary ? "text-primary" : "text-muted-foreground"
          }`}
        >
          {label}
        </p>
        <p className="text-2xl font-semibold metric-value">
          {value.toLocaleString()}
          {suffix && <span className="text-base text-muted-foreground/80">{suffix}</span>}
        </p>
        {sub && <p className="text-xs text-muted-foreground metric-value">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function RunCard({ run }: { run: RunHistoryEntry }) {
  const max = Math.max(...run.steps.map((s) => s.raw_tokens), 1);
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-baseline justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-[14px] font-medium truncate">
              {run.ask || "(empty ask)"}
            </CardTitle>
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-0.5">
              <span>{fmtRelative(run.ts)}</span>
              <span className="text-muted-foreground/40">·</span>
              <span>{run.summary.elapsed_ms} ms</span>
              <span className="text-muted-foreground/40">·</span>
              <span>{run.summary.tool_calls} call{run.summary.tool_calls === 1 ? "" : "s"}</span>
              {run.matched_intent && (
                <>
                  <span className="text-muted-foreground/40">·</span>
                  <span className="font-mono">{run.matched_intent.label}</span>
                </>
              )}
            </div>
          </div>
          <Badge variant="default" className="text-[10px] flex-none">
            {run.summary.saved_percent}% saved
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {run.steps.map((step, i) => {
          const src = lookupSource(step.tool);
          const Icon = src.icon;
          const sentPct = (step.sent_tokens / max) * 100;
          const savedPct = (step.saved_tokens / max) * 100;
          const ratio =
            step.raw_tokens > 0
              ? Math.round((step.saved_tokens / step.raw_tokens) * 100)
              : 0;
          return (
            <div key={i} className="space-y-1">
              <div className="flex items-baseline justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="inline-flex w-6 h-6 rounded-md border border-border items-center justify-center text-muted-foreground flex-none">
                    <Icon className="w-3 h-3" />
                  </span>
                  <span className="text-[12px] font-mono truncate">{step.tool}</span>
                </div>
                <div className="flex items-baseline gap-2 flex-none">
                  <span className="text-[11px] metric-value text-muted-foreground">
                    <span className="text-foreground">
                      {step.sent_tokens.toLocaleString()}
                    </span>
                    <span className="mx-1">/</span>
                    {step.raw_tokens.toLocaleString()}
                  </span>
                  <span className="text-[10px] metric-value text-muted-foreground">
                    {ratio}%
                  </span>
                </div>
              </div>
              <div className="relative h-1 rounded-full bg-muted overflow-hidden">
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
      </CardContent>
    </Card>
  );
}
