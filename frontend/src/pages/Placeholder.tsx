import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import ResultSkeleton from "@/components/ResultSkeleton";

const TOOLS = [
  { slug: "GITHUB_LIST_ISSUES", label: "GitHub Issues", args: { per_page: 5 } },
  { slug: "GITHUB_GET_A_REPOSITORY", label: "GitHub Repo", args: {} },
  { slug: "GMAIL_SEARCH_EMAILS", label: "Gmail Search", args: { query: "bug", max_results: 3 } },
  { slug: "SLACK_SEARCH_MESSAGES", label: "Slack Messages", args: { query: "bug", count: 4 } },
];

export default function Placeholder() {
  const [selectedTool, setSelectedTool] = useState(TOOLS[0].slug);
  const [result, setResult] = useState<any>(null);
  const [hydrated, setHydrated] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [hydrating, setHydrating] = useState(false);

  const tool = TOOLS.find((t) => t.slug === selectedTool);

  const run = async () => {
    if (!tool) return;
    setLoading(true);
    const res = await apiPost("/api/compress/placeholder", {
      tool_slug: tool.slug,
      arguments: tool.args,
      mode: "balanced",
      include_sample: true,
      sample_size: 3,
    });
    setResult(res);
    setHydrated(null);
    setLoading(false);
  };

  const doHydrate = async (fieldPath?: string, index?: number) => {
    if (!result?.ref_id) return;
    setHydrating(true);
    try {
      const params = new URLSearchParams();
      if (fieldPath) params.set("field_path", fieldPath);
      if (index !== undefined) params.set("index", String(index));
      const res = await fetch(`/api/hydrate/${result.ref_id}?${params}`).then((r) => r.json());
      setHydrated(res);
    } finally {
      setHydrating(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Lazy Hydration</h1>
        <p className="text-muted-foreground mt-1">
          Phase 2: Send placeholders to the LLM instead of full results. The full data is cached
          server-side and can be hydrated on demand with zero quality loss.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4 flex-wrap items-end">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Tool</label>
            <div className="relative">
              <select
                value={selectedTool}
                onChange={(e) => setSelectedTool(e.target.value)}
                className="w-56 h-9 px-3 rounded-md border bg-background text-sm appearance-none"
              >
                {TOOLS.map((t) => (
                  <option key={t.slug} value={t.slug}>{t.label}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
            </div>
          </div>
          <Button onClick={run} disabled={loading}>
            {loading ? "Creating Placeholder..." : "Create Placeholder"}
          </Button>
        </CardContent>
      </Card>

      {loading && <ResultSkeleton cards={3} showDetail={false} />}

      {!loading && result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Raw Result</p>
                <p className="text-2xl font-semibold text-rose-600">
                  {result.raw_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">tokens</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Standard Compression</p>
                <p className="text-2xl font-semibold text-amber-600">
                  {result.compressed_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">tokens</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Placeholder</p>
                <p className="text-2xl font-semibold text-emerald-600">
                  {result.placeholder_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  {result.savings_percent_vs_raw}% saved vs raw
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Placeholder Payload</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Badge variant="outline">ref: {result.ref_id}</Badge>
                <Badge variant="secondary">{result.tool_slug}</Badge>
              </div>
              <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-64">
                {JSON.stringify(result.placeholder, null, 2)}
              </pre>
              <div className="flex gap-2 flex-wrap">
                <Button size="sm" variant="outline" onClick={() => doHydrate()} disabled={hydrating}>
                  {hydrating ? "Hydrating..." : "Hydrate Full Result"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => doHydrate("title", 0)} disabled={hydrating}>
                  Hydrate: title[0]
                </Button>
                <Button size="sm" variant="outline" onClick={() => doHydrate("user.login", 0)} disabled={hydrating}>
                  Hydrate: user.login[0]
                </Button>
              </div>
            </CardContent>
          </Card>

          {hydrated && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Hydrated Result</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2 mb-2">
                  <Badge>field: {hydrated.field_path || "full"}</Badge>
                  <Badge>index: {hydrated.index ?? "all"}</Badge>
                  <Badge variant="secondary">{hydrated.hydrated_tokens.toLocaleString()} tokens</Badge>
                </div>
                <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-64">
                  {JSON.stringify(hydrated.hydrated, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
