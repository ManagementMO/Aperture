import { useEffect, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ComposingSpinner } from "@/components/ComposingSpinner";
import { Check, ShieldCheck, X } from "lucide-react";

interface BenchmarkRow {
  name: string;
  toolkit: string;
  raw_tokens: number;
  compressed_tokens: number;
  tokens_saved: number;
  compression_ratio: number;
  strategy: string;
  mode: string;
}

interface Probe {
  tool: string;
  label: string;
  passed: boolean;
}

interface ScenarioQuality {
  name: string;
  description: string;
  tokens_raw: number;
  tokens_sent: number;
  saved_percent: number;
  quality_passed: boolean;
  probes: Probe[];
}

const MODE_BLURB: Record<string, string> = {
  off: "Pass-through. Baseline.",
  safe: "Drop nulls + URL bookkeeping.",
  balanced: "Default. Flatten + sample without losing signal.",
  low: "Tighter caps and denser tables.",
  aggressive: "Squeeze prose; gated by quality probes.",
};

const MODE_ORDER = ["off", "safe", "balanced", "low", "aggressive"];

export default function Benchmarks() {
  const [rows, setRows] = useState<BenchmarkRow[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioQuality[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([
      apiGet<{ benchmarks: BenchmarkRow[] }>("/api/benchmarks"),
      apiGet<{ scenarios: ScenarioQuality[] }>("/api/quality"),
    ])
      .then(([b, q]) => {
        if (!mounted) return;
        if (b.status === "fulfilled") setRows(b.value.benchmarks ?? []);
        else setError(describeApiError(b.reason));
        if (q.status === "fulfilled") setScenarios(q.value.scenarios ?? []);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <ComposingSpinner size="md" />
      </div>
    );
  }

  // Aggregate per-mode
  const modeStats = MODE_ORDER.map((mode) => {
    const matching = rows.filter((r) => r.mode === mode);
    if (matching.length === 0) return null;
    const totalRaw = matching.reduce((s, r) => s + r.raw_tokens, 0);
    const totalSent = matching.reduce((s, r) => s + r.compressed_tokens, 0);
    const pct = totalRaw > 0 ? ((totalRaw - totalSent) / totalRaw) * 100 : 0;
    return { mode, totalRaw, totalSent, pct };
  }).filter((x): x is NonNullable<typeof x> => x !== null);

  const allPassed = scenarios.every((s) => s.quality_passed);
  const totalProbes = scenarios.reduce((s, sc) => s + sc.probes.length, 0);
  const passedProbes = scenarios.reduce(
    (s, sc) => s + sc.probes.filter((p) => p.passed).length,
    0,
  );

  return (
    <div className="space-y-7">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Benchmarks
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">
          Compression × quality
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
          Two questions only. Did Quava shrink the payload? Did the agent
          still get to read the values it needed? Numbers measured by Quava.
        </p>
      </div>

      {error && (
        <Card className="border-rose-500/40">
          <CardContent className="pt-4 pb-4">
            <p className="text-[12px] text-rose-300">{error}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-baseline justify-between">
            <CardTitle className="text-[13px] font-medium">By compression mode</CardTitle>
            <span className="text-[11px] text-muted-foreground">across all datasets</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {modeStats.map(({ mode, totalRaw, totalSent, pct }) => (
            <div key={mode} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <p className="text-sm font-medium capitalize">{mode}</p>
                  <p className="text-[11px] text-muted-foreground">{MODE_BLURB[mode]}</p>
                </div>
                <div className="flex items-baseline gap-2 flex-none">
                  <span className="text-[11px] metric-value text-muted-foreground">
                    <span className="text-foreground">{totalSent.toLocaleString()}</span>
                    <span className="mx-1">/</span>
                    {totalRaw.toLocaleString()}
                  </span>
                  <Badge
                    variant={mode === "off" ? "secondary" : "default"}
                    className="text-[10px]"
                  >
                    {pct.toFixed(0)}% saved
                  </Badge>
                </div>
              </div>
              <div className="relative h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 bg-primary"
                  style={{ width: `${(totalSent / Math.max(totalRaw, 1)) * 100}%` }}
                />
                <div
                  className="absolute inset-y-0 bg-foreground/20"
                  style={{
                    left: `${(totalSent / Math.max(totalRaw, 1)) * 100}%`,
                    width: `${((totalRaw - totalSent) / Math.max(totalRaw, 1)) * 100}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className={allPassed ? "border-primary/30" : "border-amber-500/40"}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                <CardTitle className="text-[13px] font-medium">Quality gate</CardTitle>
              </div>
              <p className="text-[12px] text-muted-foreground mt-1.5 max-w-2xl leading-relaxed">
                After Quava shrinks a payload it asks &quot;could the agent
                still answer with this?&quot; For every scenario we probe the
                compressed output for the concrete values it would have used
                &mdash; titles, IDs, statuses, addressees. If a probe fails the
                schema gets re-run at a lighter mode. The agent never reads a
                payload that lost signal.
              </p>
            </div>
            <Badge
              variant={allPassed ? "default" : "secondary"}
              className="text-[10px] flex-none"
            >
              {passedProbes}/{totalProbes} probes
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {scenarios.map((sc) => (
            <ScenarioRow key={sc.name} scenario={sc} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ScenarioRow({ scenario }: { scenario: ScenarioQuality }) {
  const passed = scenario.probes.filter((p) => p.passed).length;
  const total = scenario.probes.length;
  return (
    <div className="rounded-md border border-border/60 p-3 space-y-2">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] font-medium capitalize">
            {scenario.name.replace(/_/g, " ")}
          </p>
          <p className="text-[11px] text-muted-foreground">{scenario.description}</p>
        </div>
        <div className="flex items-baseline gap-2 flex-none">
          <Badge variant="default" className="text-[10px]">
            {scenario.saved_percent}% saved
          </Badge>
          <Badge
            variant={scenario.quality_passed ? "default" : "destructive"}
            className="text-[10px]"
          >
            {passed}/{total}
          </Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {scenario.probes.map((p, i) => (
          <span
            key={i}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono ${
              p.passed
                ? "border-primary/30 bg-primary/10 text-primary"
                : "border-rose-500/40 bg-rose-500/10 text-rose-300"
            }`}
            title={p.tool}
          >
            {p.passed ? <Check className="w-2.5 h-2.5" /> : <X className="w-2.5 h-2.5" />}
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}
