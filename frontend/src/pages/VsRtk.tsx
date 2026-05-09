import { useEffect, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ComposingSpinner } from "@/components/ComposingSpinner";
import { Check, ExternalLink, Sparkles, Trophy, X } from "lucide-react";

interface Probe {
  label: string;
  expected: string;
  found: boolean;
}

interface Engine {
  tokens: number;
  bytes: number;
  saved_percent: number;
  elapsed_ms: number;
  probe_pass: number;
  probe_total: number;
  probes: Probe[];
  signal_score: number;
  strategy?: string;
}

interface Fixture {
  fixture: string;
  description: string;
  item_count: number;
  raw_tokens: number;
  raw_bytes: number;
  rtk: Engine;
  aperture: Engine;
}

interface BenchSummary {
  total_probes: number;
  rtk_passed: number;
  aperture_passed: number;
  rtk_signal_rate: number;
  aperture_signal_rate: number;
}

interface BenchResponse {
  rtk_available: boolean;
  rtk_version: string | null;
  fixtures: Fixture[];
  summary: BenchSummary;
  thesis: string;
}

export default function VsRtk() {
  const [data, setData] = useState<BenchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiGet<BenchResponse>("/api/bench/rtk")
      .then((r) => mounted && setData(r))
      .catch((e) => mounted && setError(describeApiError(e)))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <ComposingSpinner size="md" label="Running rtk + Aperture" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-rose-500/40">
        <CardContent className="pt-5 pb-5">
          <p className="text-[12px] text-rose-300">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  if (!data.rtk_available) {
    return (
      <Card className="border-amber-500/40">
        <CardContent className="pt-5 pb-5 space-y-2">
          <p className="text-sm font-medium">rtk binary not found.</p>
          <p className="text-[12px] text-muted-foreground">
            Install with <span className="font-mono">brew install rtk</span>{" "}
            and reload to run the head-to-head benchmark.
          </p>
        </CardContent>
      </Card>
    );
  }

  const s = data.summary;
  const apertureWinsSignal = s.aperture_passed > s.rtk_passed;

  return (
    <div className="space-y-7">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Head-to-head
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">
          Aperture vs rtk
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl leading-relaxed">
          Same fixtures, two engines. <span className="font-mono">{data.rtk_version}</span>{" "}
          and Aperture both compress structured tool output before it reaches
          the model. The honest question isn&apos;t &ldquo;who saves more
          bytes&rdquo; &mdash; it&apos;s &ldquo;what survived?&rdquo; We probe
          5 specific records per fixture (first, quartiles, last) and check
          whether their concrete values are still in the compressed payload
          the model would actually read.
        </p>
        <a
          href="https://github.com/rtk-ai/rtk"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 mt-2 text-[11px] text-primary hover:underline"
        >
          rtk-ai/rtk <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      <Card className={apertureWinsSignal ? "border-primary/40" : "border-amber-500/40"}>
        <CardContent className="pt-5 pb-5 space-y-4">
          <div className="flex items-center gap-2">
            <Trophy className="w-4 h-4 text-primary" />
            <p className="text-sm font-medium">
              Across {data.fixtures.length} fixtures &middot;{" "}
              {s.total_probes} concrete value probes
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <ScoreTile
              name="rtk"
              passed={s.rtk_passed}
              total={s.total_probes}
              rate={s.rtk_signal_rate}
              tone="rtk"
            />
            <ScoreTile
              name="Aperture"
              passed={s.aperture_passed}
              total={s.total_probes}
              rate={s.aperture_signal_rate}
              tone="aperture"
            />
          </div>
          <p className="text-[12px] text-muted-foreground leading-relaxed">
            {data.thesis}
          </p>
        </CardContent>
      </Card>

      {data.fixtures.map((f) => (
        <FixtureCard key={f.fixture} fixture={f} />
      ))}
    </div>
  );
}

function ScoreTile({
  name,
  passed,
  total,
  rate,
  tone,
}: {
  name: string;
  passed: number;
  total: number;
  rate: number;
  tone: "rtk" | "aperture";
}) {
  const pct = total > 0 ? (passed / total) * 100 : 0;
  return (
    <div
      className={`rounded-lg border p-4 ${
        tone === "aperture"
          ? "border-primary/30 bg-primary/[0.04]"
          : "border-border/60 bg-muted/20"
      }`}
    >
      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
        {name}
      </p>
      <p
        className={`text-3xl font-semibold metric-value mt-1 ${
          tone === "aperture" ? "text-primary" : "text-foreground"
        }`}
      >
        {passed}/{total}
      </p>
      <p className="text-[11px] text-muted-foreground mt-0.5">
        probes preserved &middot; {rate}% signal rate
      </p>
      <div className="mt-2 h-1 rounded-full bg-muted overflow-hidden">
        <div
          className={
            tone === "aperture" ? "h-full bg-primary" : "h-full bg-foreground/40"
          }
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function FixtureCard({ fixture }: { fixture: Fixture }) {
  const r = fixture.rtk;
  const a = fixture.aperture;
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <div>
            <CardTitle className="text-[13px] font-medium">
              {fixture.description}
            </CardTitle>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {fixture.item_count.toLocaleString()} records &middot;{" "}
              {fixture.raw_tokens.toLocaleString()} raw tokens
            </p>
          </div>
          <span className="font-mono text-[10px] text-muted-foreground/70">
            {fixture.fixture}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <EngineColumn engine={r} name="rtk" raw={fixture.raw_tokens} />
          <EngineColumn engine={a} name="Aperture" raw={fixture.raw_tokens} primary />
        </div>
      </CardContent>
    </Card>
  );
}

function EngineColumn({
  engine,
  name,
  raw,
  primary,
}: {
  engine: Engine;
  name: string;
  raw: number;
  primary?: boolean;
}) {
  const pct = (engine.tokens / Math.max(raw, 1)) * 100;
  return (
    <div
      className={`rounded-md border p-3 space-y-2.5 ${
        primary ? "border-primary/30 bg-primary/[0.04]" : "border-border/60"
      }`}
    >
      <div className="flex items-baseline justify-between">
        <p className={`text-[12px] font-medium ${primary ? "text-primary" : ""}`}>
          {name}{" "}
          {primary && (
            <Sparkles className="inline w-3 h-3 ml-0.5 text-primary" />
          )}
        </p>
        <Badge variant="default" className="text-[9px]">
          {engine.saved_percent}% saved
        </Badge>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold metric-value">
          {engine.tokens.toLocaleString()}
        </span>
        <span className="text-[10px] text-muted-foreground">
          tok &middot; {engine.elapsed_ms} ms
        </span>
      </div>

      <div className="h-1 rounded-full bg-muted overflow-hidden">
        <div
          className={primary ? "h-full bg-primary" : "h-full bg-foreground/40"}
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>

      <div className="pt-1 border-t border-border/40 space-y-1">
        <div className="flex items-baseline justify-between">
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Signal preserved
          </p>
          <span className="text-[11px] metric-value">
            <span
              className={
                engine.probe_pass === engine.probe_total
                  ? "text-primary"
                  : engine.probe_pass === 0
                  ? "text-rose-300"
                  : "text-amber-300"
              }
            >
              {engine.probe_pass}
            </span>
            /{engine.probe_total}
          </span>
        </div>
        <div className="flex flex-wrap gap-1">
          {engine.probes.map((p, i) => (
            <span
              key={i}
              title={`${p.label}: "${p.expected}"`}
              className={`inline-flex items-center gap-0.5 px-1 py-0.5 rounded border text-[9px] font-mono ${
                p.found
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-rose-500/30 bg-rose-500/5 text-rose-300"
              }`}
            >
              {p.found ? <Check className="w-2 h-2" /> : <X className="w-2 h-2" />}
              {p.label.split(" ")[0]}
            </span>
          ))}
        </div>
      </div>

      {engine.strategy && (
        <p className="text-[10px] text-muted-foreground/70 font-mono">
          strategy: {engine.strategy}
        </p>
      )}
    </div>
  );
}
