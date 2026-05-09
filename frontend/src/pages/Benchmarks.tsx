import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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

export default function Benchmarks() {
  const [data, setData] = useState<BenchmarkRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet("/api/benchmarks").then((res) => {
      setData(res.benchmarks || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <p className="text-muted-foreground">Running real benchmarks...</p>;

  const byToolkit = data.reduce((acc, row) => {
    if (!acc[row.toolkit]) acc[row.toolkit] = [];
    acc[row.toolkit].push(row);
    return acc;
  }, {} as Record<string, BenchmarkRow[]>);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Benchmarks</h1>
        <p className="text-muted-foreground mt-1">
          Real compression benchmarks across all datasets and tools
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">All Benchmarks</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground text-left">
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Toolkit</th>
                <th className="pb-2 font-medium text-right">Raw</th>
                <th className="pb-2 font-medium text-right">Compressed</th>
                <th className="pb-2 font-medium text-right">Saved</th>
                <th className="pb-2 font-medium text-right">Ratio</th>
                <th className="pb-2 font-medium">Mode</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((row, i) => (
                <tr key={i}>
                  <td className="py-2 font-mono text-xs">{row.name}</td>
                  <td className="py-2">
                    <Badge variant="secondary">{row.toolkit}</Badge>
                  </td>
                  <td className="py-2 text-right font-mono">{row.raw_tokens.toLocaleString()}</td>
                  <td className="py-2 text-right font-mono">{row.compressed_tokens.toLocaleString()}</td>
                  <td className="py-2 text-right font-mono text-emerald-600">
                    {row.tokens_saved.toLocaleString()}
                  </td>
                  <td className="py-2 text-right font-mono">
                    {row.compression_ratio.toFixed(2)}
                  </td>
                  <td className="py-2">
                    <Badge variant="outline">{row.mode}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {Object.entries(byToolkit).map(([toolkit, rows]) => {
        const balanced = rows.find((r) => r.mode === "balanced");
        if (!balanced) return null;
        const savedPct = balanced.raw_tokens > 0
          ? ((balanced.tokens_saved / balanced.raw_tokens) * 100).toFixed(0)
          : "0";
        return (
          <Card key={toolkit}>
            <CardContent className="pt-6">
              <div className="flex justify-between items-center">
                <p className="font-medium">{toolkit}</p>
                <p className="font-mono text-emerald-600">{savedPct}% saved</p>
              </div>
              <p className="text-xs text-muted-foreground">
                {balanced.raw_tokens.toLocaleString()} → {balanced.compressed_tokens.toLocaleString()} tokens
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
