import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Banknote,
  Flame,
  Recycle,
  Sparkles,
  TrendingDown,
  Trash2,
} from "lucide-react";

interface Step {
  tool: string;
  raw_tokens: number;
  sent_tokens: number;
  saved_tokens: number;
  saved_percent: number;
  elapsed_ms: number;
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

interface RunHistoryEntry {
  ts: number;
  ask: string;
  answer: string;
  model: string;
  summary: Summary;
  steps: Step[];
  cost?: CostBlock | null;
  served_from_cache?: boolean;
}

const HISTORY_KEY = "aperture.runs.v1";

// Per-model pricing (USD per 1M tokens), mirrors the backend table.
const PRICING: Record<
  string,
  { input: number; output: number; cache_read: number; cache_write: number }
> = {
  "claude-haiku-4-5": { input: 1.0, output: 5.0, cache_read: 0.1, cache_write: 1.25 },
  "claude-sonnet-4-6": { input: 3.0, output: 15.0, cache_read: 0.3, cache_write: 3.75 },
  "claude-opus-4-7": { input: 15.0, output: 75.0, cache_read: 1.5, cache_write: 18.75 },
};

function whatIfCost(cost: CostBlock, target: keyof typeof PRICING): number {
  const p = PRICING[target];
  return (
    (cost.input_tokens * p.input +
      cost.cache_read_tokens * p.cache_read +
      cost.cache_write_tokens * p.cache_write +
      cost.output_tokens * p.output) /
    1_000_000
  );
}

function fmtUsd(v: number, precision = 6): string {
  if (Math.abs(v) < 1e-6) return "$0.000000";
  if (Math.abs(v) < 0.01) return `$${v.toFixed(precision)}`;
  if (Math.abs(v) < 1) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

function toolFamily(slug: string): string {
  return slug.split("_")[0] || "OTHER";
}

export default function SpendStudio() {
  const [runs, setRuns] = useState<RunHistoryEntry[]>([]);

  useEffect(() => {
    const load = (): void => {
      const raw = window.localStorage.getItem(HISTORY_KEY);
      setRuns(raw ? JSON.parse(raw) : []);
    };
    load();
    const onRun = (): void => load();
    window.addEventListener("aperture:run", onRun);
    window.addEventListener("storage", onRun);
    return () => {
      window.removeEventListener("aperture:run", onRun);
      window.removeEventListener("storage", onRun);
    };
  }, []);

  const stats = useMemo(() => {
    if (runs.length === 0) return null;

    let totalActual = 0;
    let totalCounterfactual = 0;
    let totalCacheHits = 0;
    let totalRaw = 0;
    let totalSent = 0;
    let totalElapsedMs = 0;
    let composioMade = 0;
    let composioAvoided = 0;
    let composioSavedUsd = 0;
    const familyCost: Record<string, { actual: number; counterfactual: number; calls: number; saved: number }> = {};
    const whatIf: Record<string, number> = { haiku: 0, sonnet: 0, opus: 0 };

    let firstTs = runs[runs.length - 1].ts;
    const lastTs = runs[0].ts;

    for (const r of runs) {
      totalRaw += r.summary.raw_tokens;
      totalSent += r.summary.sent_tokens;
      totalElapsedMs += r.summary.elapsed_ms;

      composioMade += r.summary.composio_calls_made ?? 0;
      composioAvoided += r.summary.composio_calls_avoided ?? 0;
      composioSavedUsd += r.summary.composio_cost_avoided_usd ?? 0;

      if (r.served_from_cache) totalCacheHits += 1;

      if (r.cost) {
        totalActual += r.served_from_cache ? 0 : r.cost.actual_usd;
        totalCounterfactual += r.cost.counterfactual_usd;
        whatIf.haiku += r.served_from_cache ? 0 : whatIfCost(r.cost, "claude-haiku-4-5");
        whatIf.sonnet += r.served_from_cache ? 0 : whatIfCost(r.cost, "claude-sonnet-4-6");
        whatIf.opus += r.served_from_cache ? 0 : whatIfCost(r.cost, "claude-opus-4-7");
      }

      // Per-tool family attribution: split actual_usd by token weight.
      if (r.cost && !r.served_from_cache && r.steps.length > 0) {
        const totalSentInRun = r.steps.reduce((s, st) => s + st.sent_tokens, 0) || 1;
        for (const st of r.steps) {
          const fam = toolFamily(st.tool);
          const share = st.sent_tokens / totalSentInRun;
          familyCost[fam] = familyCost[fam] || { actual: 0, counterfactual: 0, calls: 0, saved: 0 };
          familyCost[fam].actual += r.cost.actual_usd * share;
          familyCost[fam].counterfactual += r.cost.counterfactual_usd * share;
          familyCost[fam].saved += r.cost.saved_usd * share;
          familyCost[fam].calls += 1;
        }
      }
    }

    const sessionMinutes = Math.max(1, (lastTs - firstTs) / 60000);
    const burnPerMin = totalActual / sessionMinutes;
    const projectedDaily = burnPerMin * 60 * 8;   // 8-hour active day

    const families = Object.entries(familyCost)
      .map(([name, v]) => ({ name, ...v }))
      .sort((a, b) => b.actual - a.actual);

    return {
      runCount: runs.length,
      cacheHits: totalCacheHits,
      totalActual,
      totalCounterfactual,
      totalSavedUsd: totalCounterfactual - totalActual,
      totalRaw,
      totalSent,
      totalElapsedMs,
      whatIf,
      families,
      sessionMinutes,
      burnPerMin,
      projectedDaily,
      composioMade,
      composioAvoided,
      composioSavedUsd,
    };
  }, [runs]);

  const clearHistory = (): void => {
    if (!confirm("Clear all session run history?")) return;
    window.localStorage.removeItem(HISTORY_KEY);
    setRuns([]);
  };

  if (!stats) {
    return (
      <div className="space-y-7">
        <Header />
        <Card>
          <CardContent className="pt-5 pb-5 text-center space-y-2">
            <p className="text-sm text-muted-foreground">No runs yet.</p>
            <p className="text-[12px] text-muted-foreground">
              Head over to <span className="font-mono">/run</span> and ask the
              agent something. The Spend Studio fills in as you go.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const savedPct =
    stats.totalCounterfactual > 0
      ? (stats.totalSavedUsd / stats.totalCounterfactual) * 100
      : 0;

  return (
    <div className="space-y-7">
      <Header />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <BigTile
          label="Spent this session"
          value={fmtUsd(stats.totalActual)}
          sublabel={`${stats.runCount} run${stats.runCount === 1 ? "" : "s"}`}
          icon={<Banknote className="w-3.5 h-3.5" />}
        />
        <BigTile
          label="Saved vs uncompressed"
          primary
          value={fmtUsd(stats.totalSavedUsd)}
          sublabel={`${savedPct.toFixed(0)}% cheaper · ${(stats.totalRaw - stats.totalSent).toLocaleString()} tok cut`}
          icon={<TrendingDown className="w-3.5 h-3.5" />}
        />
        <BigTile
          label="Cache hits"
          value={`${stats.cacheHits}`}
          sublabel={
            stats.cacheHits > 0
              ? `${((stats.cacheHits / stats.runCount) * 100).toFixed(0)}% of runs · $0 each`
              : "(re-ask the same Q in 5 min)"
          }
          icon={<Recycle className="w-3.5 h-3.5" />}
        />
        <BigTile
          label="Daily burn at this rate"
          value={fmtUsd(stats.projectedDaily, 4)}
          sublabel={`${fmtUsd(stats.burnPerMin, 4)}/min · 8h active day`}
          icon={<Flame className="w-3.5 h-3.5" />}
        />
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-baseline justify-between gap-3">
            <CardTitle className="text-[13px] font-medium">
              Composio bill — tool execution savings
            </CardTitle>
            <Badge variant="default" className="text-[10px]">
              {fmtUsd(stats.composioSavedUsd, 4)} saved
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground">
            When the agent calls the same tool with the same args twice
            within 5 minutes, the second call is served from local cache —
            Composio is not re-billed.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <SmallTile
              label="Tool calls billed"
              value={String(stats.composioMade)}
              sublabel="Composio executions"
            />
            <SmallTile
              label="Calls avoided"
              primary
              value={String(stats.composioAvoided)}
              sublabel={
                stats.composioAvoided + stats.composioMade > 0
                  ? `${(
                      (stats.composioAvoided /
                        (stats.composioAvoided + stats.composioMade)) *
                      100
                    ).toFixed(0)}% cache hit`
                  : "no traffic yet"
              }
            />
            <SmallTile
              label="Composio $ avoided"
              primary
              value={fmtUsd(stats.composioSavedUsd, 4)}
              sublabel="estimated at default rate"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-[13px] font-medium">
            What if you had used a different model?
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Same input/output token mix, different price tier. Cache costs
            scale with the chosen tier.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <ModelRow
            label="Haiku 4.5 (current)"
            cost={stats.whatIf.haiku}
            total={Math.max(stats.whatIf.opus, stats.whatIf.haiku)}
            current
          />
          <ModelRow
            label="Sonnet 4.6"
            cost={stats.whatIf.sonnet}
            total={Math.max(stats.whatIf.opus, stats.whatIf.haiku)}
          />
          <ModelRow
            label="Opus 4.7"
            cost={stats.whatIf.opus}
            total={Math.max(stats.whatIf.opus, stats.whatIf.haiku)}
          />
          <p className="text-[11px] text-muted-foreground pt-1">
            Opus would have been{" "}
            <span className="num text-foreground">
              {(stats.whatIf.opus / Math.max(stats.whatIf.haiku, 1e-9)).toFixed(0)}×
            </span>{" "}
            more expensive than your current Haiku spend.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-baseline justify-between">
            <CardTitle className="text-[13px] font-medium">
              Where the money went · by tool family
            </CardTitle>
            <span className="text-[10px] text-muted-foreground">
              {stats.families.length} families
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {stats.families.map((f) => (
            <FamilyRow
              key={f.name}
              name={f.name}
              actual={f.actual}
              saved={f.saved}
              calls={f.calls}
              maxActual={stats.families[0].actual}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3 flex-row items-center justify-between">
          <div>
            <CardTitle className="text-[13px] font-medium">
              Recent runs
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              From localStorage. Stays on your machine.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={clearHistory}
            className="text-[11px] gap-1"
          >
            <Trash2 className="w-3 h-3" /> Clear
          </Button>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {runs.slice(0, 12).map((r) => (
            <RunRow key={r.ts} run={r} />
          ))}
          {runs.length > 12 && (
            <p className="text-[11px] text-muted-foreground/70 pt-1">
              + {runs.length - 12} more runs
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Header() {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        Cost intelligence
      </p>
      <h1 className="text-3xl font-semibold tracking-tight mt-1">
        Spend Studio
      </h1>
      <p className="text-sm text-muted-foreground mt-2 max-w-3xl leading-relaxed">
        Every run you make is measured. Aperture rolls them up into a
        per-tool cost map, what-if comparisons across model tiers, and a
        burn-rate projection. Cache hits cost $0 and are counted separately.
      </p>
    </div>
  );
}

function SmallTile({
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
    <div
      className={`rounded-md border p-2.5 ${
        primary ? "border-primary/30 bg-primary/[0.04]" : "border-border/40"
      }`}
    >
      <p className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p
        className={`text-[16px] font-semibold metric-value mt-0.5 ${
          primary ? "text-primary" : ""
        }`}
      >
        {value}
      </p>
      {sublabel && (
        <p className="text-[9px] text-muted-foreground/80 metric-value">
          {sublabel}
        </p>
      )}
    </div>
  );
}

function BigTile({
  label,
  value,
  sublabel,
  icon,
  primary,
}: {
  label: string;
  value: string;
  sublabel: string;
  icon?: React.ReactNode;
  primary?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        primary
          ? "border-primary/30 bg-primary/[0.04]"
          : "border-border/60 bg-card/40"
      }`}
    >
      <div className="flex items-center gap-1.5">
        {icon && <span className={primary ? "text-primary" : "text-muted-foreground"}>{icon}</span>}
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </p>
      </div>
      <p className={`text-2xl font-semibold metric-value mt-1 ${primary ? "text-primary" : ""}`}>
        {value}
      </p>
      <p className="text-[10px] text-muted-foreground/80 mt-0.5">{sublabel}</p>
    </div>
  );
}

function ModelRow({
  label,
  cost,
  total,
  current,
}: {
  label: string;
  cost: number;
  total: number;
  current?: boolean;
}) {
  const pct = total > 0 ? (cost / total) * 100 : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <p className={`text-[12px] ${current ? "font-medium text-primary" : ""}`}>
          {label} {current && <Sparkles className="inline w-3 h-3 ml-0.5" />}
        </p>
        <span className="font-mono text-[11px] metric-value">
          {fmtUsd(cost, 4)}
        </span>
      </div>
      <div className="h-1 rounded-full bg-muted overflow-hidden">
        <div
          className={current ? "h-full bg-primary" : "h-full bg-foreground/30"}
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
    </div>
  );
}

function FamilyRow({
  name,
  actual,
  saved,
  calls,
  maxActual,
}: {
  name: string;
  actual: number;
  saved: number;
  calls: number;
  maxActual: number;
}) {
  const pct = maxActual > 0 ? (actual / maxActual) * 100 : 0;
  const savedPct = actual + saved > 0 ? (saved / (actual + saved)) * 100 : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className="text-[12px] font-medium">{name}</p>
          <p className="text-[10px] text-muted-foreground">
            {calls} call{calls === 1 ? "" : "s"} · saved {fmtUsd(saved, 4)} ({savedPct.toFixed(0)}%)
          </p>
        </div>
        <span className="font-mono text-[12px] metric-value">{fmtUsd(actual, 4)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className="h-full bg-primary" style={{ width: `${Math.max(2, pct)}%` }} />
      </div>
    </div>
  );
}

function RunRow({ run }: { run: RunHistoryEntry }) {
  const cost = run.cost?.actual_usd ?? 0;
  const saved = run.cost?.saved_usd ?? 0;
  const time = new Date(run.ts).toLocaleTimeString();

  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 border-b border-border/30 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="text-[12px] truncate">{run.ask}</p>
        <p className="text-[10px] text-muted-foreground">
          {time} &middot; {run.summary.tool_calls} tool{" "}
          {run.served_from_cache && (
            <Badge variant="default" className="text-[9px] ml-1">
              cached · $0
            </Badge>
          )}
        </p>
      </div>
      <div className="text-right flex-none">
        <p className="font-mono text-[11px] metric-value">
          {run.served_from_cache ? "$0.000000" : fmtUsd(cost)}
        </p>
        {!run.served_from_cache && saved > 0 && (
          <p className="text-[10px] text-primary metric-value">
            saved {fmtUsd(saved, 4)}
          </p>
        )}
      </div>
    </div>
  );
}
