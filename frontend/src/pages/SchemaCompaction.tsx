import { useEffect, useMemo, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ComposingSpinner } from "@/components/ComposingSpinner";

interface SchemaSample {
  name: string;
  json: string;
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
          Tool definitions sit in every prompt. Quava reshapes them into a
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
        <SideBySide sample={active} samples={samples} activeIndex={activeIndex} setActiveIndex={setActiveIndex} />
      )}
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

function SideBySide({
  sample,
  samples,
  activeIndex,
  setActiveIndex,
}: {
  sample: SchemaSample;
  samples: SchemaSample[];
  activeIndex: number;
  setActiveIndex: (i: number) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <CardTitle className="text-[13px] font-medium font-mono">
            {sample.name}
          </CardTitle>
          <div className="flex flex-wrap gap-1.5">
            {samples.map((s, i) => (
              <button
                key={s.name}
                type="button"
                onClick={() => setActiveIndex(i)}
                className={`text-[11px] px-2 py-0.5 rounded-md border transition-colors ${
                  i === activeIndex
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground hover:border-primary/40"
                }`}
              >
                {s.name.split("_").slice(0, 2).join(" ").toLowerCase()}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          <Pane
            title="What the LLM used to see"
            tokens={sample.json_tokens}
            tone="neutral"
            content={sample.json}
            isJson
          />
          <Pane
            title="What Quava sends instead"
            tokens={sample.compact_tokens}
            tone="primary"
            content={sample.compact}
            isJson={false}
            badge={`${sample.savings_percent}% smaller`}
          />
        </div>
        <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>
            Same fields, same call signature &mdash; just fewer tokens to ship.
          </span>
          <span className="metric-value">
            {sample.json_tokens} → {sample.compact_tokens} ({sample.saved} saved)
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function Pane({
  title,
  tokens,
  tone,
  content,
  isJson,
  badge,
}: {
  title: string;
  tokens: number;
  tone: "neutral" | "primary";
  content: string;
  isJson: boolean;
  badge?: string;
}) {
  // Animated reveal on mount so the user sees both panes "type in" once,
  // even though the data is fully loaded.
  const [revealed, setRevealed] = useState(0);
  const total = content.length;
  const visibleContent = useMemo(() => content.slice(0, revealed), [content, revealed]);
  const cursorVisible = revealed < total;

  useEffect(() => {
    let raf = 0;
    if (!total) {
      raf = requestAnimationFrame(() => setRevealed(0));
      return () => cancelAnimationFrame(raf);
    }

    let startedAt = 0;
    const durationMs = 900;
    const step = () => {
      if (startedAt === 0) {
        startedAt = performance.now();
        setRevealed(0);
      }
      const elapsed = performance.now() - startedAt;
      const ratio = Math.min(1, elapsed / durationMs);
      setRevealed(Math.floor(ratio * total));
      if (ratio < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [content, total]);

  const baseHeader =
    tone === "primary"
      ? "border-primary/40 bg-primary/5"
      : "border-border bg-muted/20";

  return (
    <div className={`rounded-md border ${baseHeader} overflow-hidden flex flex-col`}>
      <div className="px-3 py-2 flex items-center justify-between border-b border-border/50">
        <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{title}</p>
        <div className="flex items-center gap-2">
          {badge && (
            <Badge variant="default" className="text-[10px]">
              {badge}
            </Badge>
          )}
          <span className="text-[11px] metric-value text-muted-foreground">
            {tokens} tokens
          </span>
        </div>
      </div>
      <pre
        className={`p-3 text-[11px] font-mono leading-relaxed overflow-auto whitespace-pre-wrap min-h-[260px] max-h-[420px] ${
          isJson ? "text-foreground/80" : "text-foreground"
        }`}
      >
        {visibleContent}
        {cursorVisible && <span className="text-primary aperture-pulse">▌</span>}
      </pre>
    </div>
  );
}
