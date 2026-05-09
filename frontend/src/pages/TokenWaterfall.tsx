import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface WaterfallStep {
  tool_slug: string;
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

export default function TokenWaterfall() {
  const [data, setData] = useState<WaterfallData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet("/api/waterfall").then((res) => {
      setData(res);
      setLoading(false);
    });
  }, []);

  if (loading) return <p className="text-muted-foreground">Loading real measurements...</p>;
  if (!data) return <p className="text-muted-foreground">No data</p>;

  // const total = data.total_raw + data.schema_tokens + data.argument_tokens;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Token Waterfall</h1>
        <p className="text-muted-foreground mt-1">
          Real measured token flow from a multi-tool agent run
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Raw</p>
            <p className="text-2xl font-semibold">{data.total_raw.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">tool result tokens</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Compressed</p>
            <p className="text-2xl font-semibold text-emerald-600">{data.total_compressed.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">after Aperture</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Saved</p>
            <p className="text-2xl font-semibold text-blue-600">{data.total_saved.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">{data.overall_reduction.toFixed(1)}% reduction</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Run Steps (Measured)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.steps.map((step, i) => {
            return (
              <div key={i} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="font-mono text-xs">{step.tool_slug}</span>
                  <span className="font-mono">
                    {step.raw_tokens.toLocaleString()} → {step.compressed_tokens.toLocaleString()}
                    {" "}({step.tokens_saved > 0 ? `-${step.tokens_saved.toLocaleString()}` : "0"})
                  </span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-emerald-500"
                    style={{ width: `${(step.compressed_tokens / step.raw_tokens) * 100}%` }}
                  />
                  <div
                    className="h-full bg-rose-400"
                    style={{ width: `${(step.tokens_saved / step.raw_tokens) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{step.strategy}</p>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
