import { useEffect, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ComposingSpinner } from "@/components/ComposingSpinner";
import {
  Database,
  FileText,
  GitBranch,
  ListTodo,
  Mail,
  MessageSquare,
} from "lucide-react";

interface WaterfallStep {
  tool_slug: string;
  label: string;
  source: string;
  raw_tokens: number;
  compressed_tokens: number;
  tokens_saved: number;
  strategy: string;
}

interface WaterfallData {
  steps: WaterfallStep[];
  total_raw: number;
  total_compressed: number;
  total_saved: number;
  schema_tokens: number;
  argument_tokens: number;
  overall_reduction: number;
}

const SOURCE_ICON: Record<string, typeof GitBranch> = {
  GitHub: GitBranch,
  Gmail: Mail,
  Slack: MessageSquare,
  Notion: FileText,
  Linear: ListTodo,
  Supabase: Database,
};

export default function TokenWaterfall() {
  const [data, setData] = useState<WaterfallData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<WaterfallData>("/api/waterfall")
      .then((res) => setData(res))
      .catch((err) => setError(describeApiError(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <ComposingSpinner size="md" label="Composing" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Card className="border-rose-500/40">
        <CardContent className="pt-5 pb-5 space-y-1">
          <p className="text-sm font-medium text-rose-400">Couldn&apos;t load waterfall.</p>
          <p className="text-[12px] text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const max = Math.max(...data.steps.map((s) => s.raw_tokens), 1);

  return (
    <div className="space-y-7">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Token waterfall
        </p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Per-tool flow</h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
          One agent run touches several tools. Aperture watches every payload
          between the tool and the model. Numbers measured by Aperture.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Raw" value={data.total_raw} sub="tokens from tools" />
        <Stat label="Sent" value={data.total_compressed} sub="tokens to LLM" />
        <Stat
          label="Saved"
          value={data.total_saved}
          sub={`${data.overall_reduction.toFixed(1)}% reduction`}
          primary
        />
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-[13px] font-medium">Run steps</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.steps.map((step, i) => {
            const Icon = SOURCE_ICON[step.source] ?? GitBranch;
            const sentPct = (step.compressed_tokens / max) * 100;
            const savedPct = (step.tokens_saved / max) * 100;
            const savedRatio =
              step.raw_tokens > 0
                ? Math.round((step.tokens_saved / step.raw_tokens) * 100)
                : 0;
            return (
              <div key={i} className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="inline-flex w-7 h-7 rounded-md border border-border items-center justify-center text-muted-foreground flex-none">
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{step.label}</p>
                      <p className="text-[11px] font-mono text-muted-foreground truncate">
                        {step.tool_slug}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2 flex-none">
                    <span className="text-[11px] metric-value text-muted-foreground">
                      <span className="text-foreground">
                        {step.compressed_tokens.toLocaleString()}
                      </span>
                      <span className="mx-1">/</span>
                      {step.raw_tokens.toLocaleString()}
                    </span>
                    <Badge variant="default" className="text-[10px]">
                      {savedRatio}% saved
                    </Badge>
                  </div>
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
          <div className="flex items-center gap-3 pt-2 text-[10px] text-muted-foreground border-t border-border/40">
            <span className="flex items-center gap-1 pt-2">
              <span className="w-2 h-2 rounded-sm bg-primary" /> sent to LLM
            </span>
            <span className="flex items-center gap-1 pt-2">
              <span className="w-2 h-2 rounded-sm bg-foreground/20" /> compressed away
            </span>
            <span className="ml-auto pt-2 metric-value">
              schemas + arguments add {data.schema_tokens + data.argument_tokens} tokens
            </span>
          </div>
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
