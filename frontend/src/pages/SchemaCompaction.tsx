import { useEffect, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ComposingSpinner } from "@/components/ComposingSpinner";

interface SchemaSample {
  name: string;
  compact: string;
  json_tokens: number;
  compact_tokens: number;
  saved: number;
  savings_percent: number;
}

interface SampleResponse {
  samples: SchemaSample[];
}

export default function SchemaCompaction() {
  const [samples, setSamples] = useState<SchemaSample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    apiGet<SampleResponse>("/api/schema/sample")
      .then((res) => setSamples(res.samples ?? []))
      .catch((err) => setError(describeApiError(err)))
      .finally(() => setLoading(false));
  }, []);

  // Auto-rotate through samples every 4 seconds for the demo "always working" feel.
  useEffect(() => {
    if (samples.length < 2) return;
    const id = window.setInterval(() => {
      setActiveIndex((i) => (i + 1) % samples.length);
    }, 4500);
    return () => window.clearInterval(id);
  }, [samples.length]);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <ComposingSpinner size="md" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-rose-500/40">
        <CardContent className="pt-5 pb-5 space-y-1">
          <p className="text-sm font-medium text-rose-400">Couldn&apos;t load schemas.</p>
          <p className="text-[12px] text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const totalJson = samples.reduce((s, x) => s + x.json_tokens, 0);
  const totalCompact = samples.reduce((s, x) => s + x.compact_tokens, 0);
  const totalSaved = totalJson - totalCompact;
  const totalPct = totalJson > 0 ? Math.round((totalSaved / totalJson) * 100) : 0;
  const active = samples[activeIndex];

  return (
    <div className="space-y-7">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Schema compaction
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">
          Tool schemas, smaller
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
          Tool definitions sit in every prompt. Aperture reshapes them into a
          dense single-line form an LLM can still read &mdash; same call signatures,
          fewer tokens spent before the agent has even said anything.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Original" value={totalJson} sub="JSON tokens" />
        <Stat label="Compact" value={totalCompact} sub="dense tokens" />
        <Stat label="Saved" value={totalSaved} sub={`${totalPct}% smaller`} primary />
      </div>

      {active && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-[13px] font-medium">Live sample</CardTitle>
              <div className="flex items-center gap-1">
                {samples.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    aria-label={`Show sample ${i + 1}`}
                    onClick={() => setActiveIndex(i)}
                    className={`h-1.5 rounded-full transition-all ${
                      i === activeIndex ? "w-6 bg-primary" : "w-1.5 bg-border hover:bg-muted-foreground/40"
                    }`}
                  />
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <SchemaDiff sample={active} key={active.name} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-[13px] font-medium">All samples</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {samples.map((s, i) => (
            <button
              key={s.name}
              type="button"
              onClick={() => setActiveIndex(i)}
              className={`w-full flex items-baseline justify-between gap-3 px-2 py-1.5 rounded-md text-left transition-colors ${
                i === activeIndex
                  ? "bg-primary/5 border border-primary/30"
                  : "hover:bg-muted/40 border border-transparent"
              }`}
            >
              <span className="font-mono text-[12px] truncate">{s.name}</span>
              <span className="flex items-center gap-2 flex-none">
                <span className="text-[11px] metric-value text-muted-foreground">
                  <span className="text-foreground">{s.compact_tokens}</span>
                  <span className="mx-1">/</span>
                  {s.json_tokens}
                </span>
                <Badge variant="default" className="text-[10px]">
                  {s.savings_percent}%
                </Badge>
              </span>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  primary,
}: {
  label: string;
  value: number;
  sub?: string;
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
        <p className="text-2xl font-semibold metric-value">{value.toLocaleString()}</p>
        {sub && <p className="text-xs text-muted-foreground metric-value">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function SchemaDiff({ sample }: { sample: SchemaSample }) {
  const [revealed, setRevealed] = useState(0);

  // Animated reveal — types out the compact form character-by-character so
  // the user sees compaction happen rather than just appear.
  useEffect(() => {
    setRevealed(0);
    if (!sample.compact) return;
    const total = sample.compact.length;
    const intervalMs = Math.max(8, Math.min(30, 1800 / total));
    const id = window.setInterval(() => {
      setRevealed((n) => {
        if (n >= total) {
          window.clearInterval(id);
          return n;
        }
        return Math.min(total, n + Math.max(1, Math.floor(total / 80)));
      });
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [sample.compact]);

  const visible = sample.compact.slice(0, revealed);
  const cursorVisible = revealed < sample.compact.length;

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <p className="font-mono text-[12px]">{sample.name}</p>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px]">
            JSON {sample.json_tokens}
          </Badge>
          <Badge variant="default" className="text-[10px]">
            Compact {sample.compact_tokens}
          </Badge>
          <Badge variant="secondary" className="text-[10px]">
            {sample.savings_percent}% smaller
          </Badge>
        </div>
      </div>

      <pre className="text-[12px] font-mono leading-relaxed bg-[#0A0A0A] border border-border/60 rounded-md p-4 overflow-auto whitespace-pre-wrap min-h-[120px]">
        <span>{visible}</span>
        {cursorVisible && (
          <span className="text-primary aperture-pulse">▌</span>
        )}
      </pre>
    </div>
  );
}
