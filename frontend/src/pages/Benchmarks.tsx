import { useEffect, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ComposingSpinner } from "@/components/ComposingSpinner";
import { Check, X } from "lucide-react";

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

interface SampleQuality {
  tool: string;
  raw_tokens: number;
  sent_tokens: number;
  saved_percent: number;
  quality: { label: string; passed: boolean }[];
}

const MODE_LABEL: Record<string, string> = {
  off: "Off",
  safe: "Safe",
  balanced: "Balanced",
  low: "Low",
  aggressive: "Aggressive",
};

const MODE_BLURB: Record<string, string> = {
  off: "Pass-through, no compression. Baseline.",
  safe: "Drop nulls and obvious bookkeeping. Conservative.",
  balanced: "Default. Flatten and prune without losing signal.",
  low: "Tighter caps, smaller samples, denser tables.",
  aggressive: "Squeeze prose; only safe at well-understood asks.",
};

export default function Benchmarks() {
  const [rows, setRows] = useState<BenchmarkRow[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioQuality[]>([]);
  const [sample, setSample] = useState<SampleQuality | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([
      apiGet<{ benchmarks: BenchmarkRow[] }>("/api/benchmarks"),
      apiGet<{ scenarios: ScenarioQuality[]; sample: SampleQuality }>("/api/quality"),
    ])
      .then(([b, q]) => {
        if (!mounted) return;
        if (b.status === "fulfilled") setRows(b.value.benchmarks ?? []);
        else setError(describeApiError(b.reason));
        if (q.status === "fulfilled") {
          setScenarios(q.value.scenarios ?? []);
          setSample(q.value.sample ?? null);
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
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

  // Group rows by mode and average savings
  const modeBuckets: Record<string, BenchmarkRow[]> = {};
  for (const row of rows) {
    if (!modeBuckets[row.mode]) modeBuckets[row.mode] = [];
    modeBuckets[row.mode].push(row);
  }
  const modeStats = Object.entries(modeBuckets).map(([mode, list]) => {
    const totalRaw = list.reduce((s, r) => s + r.raw_tokens, 0);
    const totalSent = list.reduce((s, r) => s + r.compressed_tokens, 0);
    const saved = totalRaw - totalSent;
    const pct = totalRaw > 0 ? (saved / totalRaw) * 100 : 0;
    return { mode, totalRaw, totalSent, saved, pct };
  });

  const allProbesPassed = scenarios.every((s) => s.quality_passed);

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
          Aperture is graded on two axes: how much it shrinks and whether the
          shrunken payload still answers the question. Numbers measured by Aperture.
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
          <CardTitle className="text-[13px] font-medium">Aggregate by mode</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {modeStats.map(({ mode, totalRaw, totalSent, saved, pct }) => (
            <div key={mode} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <p className="text-sm font-medium capitalize">{MODE_LABEL[mode] ?? mode}</p>
                  <p className="text-[11px] text-muted-foreground">{MODE_BLURB[mode] ?? ""}</p>
                </div>
                <div className="flex items-baseline gap-2 flex-none">
                  <span className="text-[11px] metric-value text-muted-foreground">
                    <span className="text-foreground">{totalSent.toLocaleString()}</span>
                    <span className="mx-1">/</span>
                    {totalRaw.toLocaleString()}
                  </span>
                  <Badge variant={mode === "off" ? "secondary" : "default"} className="text-[10px]">
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
                    width: `${(saved / Math.max(totalRaw, 1)) * 100}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className={allProbesPassed ? "border-primary/30" : "border-amber-500/40"}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-[13px] font-medium">Quality checker</CardTitle>
            <Badge variant={allProbesPassed ? "default" : "secondary"} className="text-[10px]">
              {allProbesPassed ? "all signals preserved" : "some regressions"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[12px] text-muted-foreground">
            For each scenario, Aperture runs concrete value probes against the
            compressed payload &mdash; the same titles, IDs, addressees, and statuses
            an agent would extract. A probe passes if the value is still
            present.
          </p>
          {scenarios.map((sc) => (
            <ScenarioBlock key={sc.name} scenario={sc} />
          ))}
          {sample && <SampleProbes sample={sample} />}
        </CardContent>
      </Card>
    </div>
  );
}

function ScenarioBlock({ scenario }: { scenario: ScenarioQuality }) {
  const totalProbes = scenario.probes.length;
  const passed = scenario.probes.filter((p) => p.passed).length;
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
          <span className="text-[11px] metric-value text-muted-foreground">
            <span className="text-foreground">{scenario.tokens_sent.toLocaleString()}</span>
            <span className="mx-1">/</span>
            {scenario.tokens_raw.toLocaleString()}
          </span>
          <Badge variant="default" className="text-[10px]">
            {scenario.saved_percent}% saved
          </Badge>
          <Badge
            variant={scenario.quality_passed ? "default" : "destructive"}
            className="text-[10px]"
          >
            {passed}/{totalProbes} probes
          </Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 pt-1">
        {scenario.probes.map((p, i) => (
          <span
            key={i}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono ${
              p.passed
                ? "border-primary/30 bg-primary/10 text-primary"
                : "border-rose-500/40 bg-rose-500/10 text-rose-300"
            }`}
            title={`${p.tool}: ${p.label}`}
          >
            {p.passed ? <Check className="w-2.5 h-2.5" /> : <X className="w-2.5 h-2.5" />}
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function SampleProbes({ sample }: { sample: SampleQuality }) {
  return (
    <div className="rounded-md border border-border/60 p-3 space-y-2 bg-muted/20">
      <div className="flex items-baseline justify-between">
        <p className="text-[12px] font-medium">Live probe · {sample.tool}</p>
        <span className="text-[11px] metric-value text-muted-foreground">
          {sample.sent_tokens.toLocaleString()} / {sample.raw_tokens.toLocaleString()} ·{" "}
          {sample.saved_percent}% saved
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {sample.quality.map((q, i) => (
          <span
            key={i}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono ${
              q.passed
                ? "border-primary/30 bg-primary/10 text-primary"
                : "border-rose-500/40 bg-rose-500/10 text-rose-300"
            }`}
          >
            {q.passed ? <Check className="w-2.5 h-2.5" /> : <X className="w-2.5 h-2.5" />}
            {q.label}
          </span>
        ))}
      </div>
    </div>
  );
}
