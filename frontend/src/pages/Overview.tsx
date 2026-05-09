import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface DatasetInfo {
  items: number;
  raw_tokens: number;
}

export default function Overview() {
  const [datasets, setDatasets] = useState<Record<string, DatasetInfo>>({});
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    apiGet("/api/health").then(setHealth);
    apiGet("/api/datasets").then(setDatasets);
  }, []);

  const totalItems = Object.values(datasets).reduce((s, d) => s + d.items, 0);
  const totalTokens = Object.values(datasets).reduce((s, d) => s + d.raw_tokens, 0);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="text-muted-foreground mt-1">
          Real token measurements from Aperture's compression engine
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Mock Datasets</p>
            <p className="text-2xl font-semibold">{Object.keys(datasets).length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Records</p>
            <p className="text-2xl font-semibold">{totalItems.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Raw Tokens</p>
            <p className="text-2xl font-semibold">{totalTokens.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">measured by tiktoken</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">API Status</p>
            <Badge variant={health?.status === "ok" ? "default" : "destructive"}>
              {health?.status === "ok" ? "Online" : "Offline"}
            </Badge>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Available Datasets</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground text-left">
                  <th className="pb-2 font-medium">Dataset</th>
                  <th className="pb-2 font-medium text-right">Items</th>
                  <th className="pb-2 font-medium text-right">Raw Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {Object.entries(datasets).map(([name, info]) => (
                  <tr key={name}>
                    <td className="py-2 font-mono text-xs">{name}</td>
                    <td className="py-2 text-right">{info.items.toLocaleString()}</td>
                    <td className="py-2 text-right font-mono">{info.raw_tokens.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">What Aperture Measures</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>Schema tokens loaded into model context</p>
            <p>Tool argument tokens per call</p>
            <p>Raw vs compressed result tokens (tiktoken)</p>
            <p>Retry and meta-tool overhead</p>
            <p>Cache hit token savings</p>
            <p>Per-tool and per-session totals</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
