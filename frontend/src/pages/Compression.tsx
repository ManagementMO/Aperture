import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CompressionResult {
  tool_slug: string;
  raw_tokens: number;
  compressed_tokens: number;
  json_tokens?: number;
  tokens_saved: number;
  compression_ratio: number;
  strategy: string;
  mode: string;
  llm_format?: string;
  llm_string_preview?: string | null;
  warnings?: string[];
}

const DATASET_TOOLS = [
  { key: "notion_pages", label: "Notion Pages", tool_slug: "NOTION_SEARCH_NOTION_PAGE" },
  { key: "linear_issues", label: "Linear Issues", tool_slug: "LINEAR_GET_LINEAR_USER_ISSUES" },
  { key: "supabase_users", label: "Supabase Users", tool_slug: "SUPABASE_FETCH_TABLE_ROWS" },
];

const MOCK_TOOLS = [
  { slug: "GITHUB_GET_A_REPOSITORY", label: "GitHub Repo" },
  { slug: "GITHUB_LIST_ISSUES", label: "GitHub Issues" },
  { slug: "GITHUB_LIST_PULL_REQUESTS", label: "GitHub PRs" },
  { slug: "GMAIL_SEARCH_EMAILS", label: "Gmail Search" },
  { slug: "SLACK_SEARCH_MESSAGES", label: "Slack Messages" },
];

const MODES = ["off", "safe", "balanced", "low", "aggressive"] as const;

export default function Compression() {
  const [mode, setMode] = useState<(typeof MODES)[number]>("balanced");
  const [results, setResults] = useState<Record<string, CompressionResult>>({});
  const [loading, setLoading] = useState<string | null>(null);

  const runDataset = async (key: string, tool_slug: string) => {
    setLoading(key);
    const res = await apiPost("/api/compress/dataset", { dataset: key, mode, tool_slug });
    setResults((prev) => ({ ...prev, [key]: res }));
    setLoading(null);
  };

  const runTool = async (slug: string) => {
    setLoading(slug);
    const res = await apiPost("/api/execute", { tool_slug: slug, arguments: {}, mode });
    setResults((prev) => ({ ...prev, [slug]: res }));
    setLoading(null);
  };

  const renderResult = (key: string, _label: string) => {
    const res = results[key];
    if (!res) {
      return (
        <p className="text-sm text-muted-foreground">
          {loading === key ? "Running real compression..." : "Click to measure"}
        </p>
      );
    }
    const savedPct = res.raw_tokens > 0 ? ((res.tokens_saved / res.raw_tokens) * 100).toFixed(0) : "0";
    const isToon = res.llm_format === "toon";
    const toonGain =
      isToon && res.json_tokens !== undefined && res.json_tokens > res.compressed_tokens
        ? Math.round(((res.json_tokens - res.compressed_tokens) / res.json_tokens) * 100)
        : null;

    return (
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-lg font-semibold text-rose-600">{res.raw_tokens.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Raw</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-emerald-600">{res.compressed_tokens.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Sent to LLM</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-blue-600">{savedPct}%</p>
            <p className="text-xs text-muted-foreground">Saved</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge variant="secondary">{res.strategy}</Badge>
          {isToon && (
            <Badge variant="default" title="Token-Oriented Object Notation">
              TOON{toonGain !== null ? ` ·  ${toonGain}% vs JSON` : ""}
            </Badge>
          )}
        </div>
        {isToon && res.llm_string_preview && (
          <pre className="text-xs bg-muted p-2 rounded-md overflow-auto max-h-40 whitespace-pre-wrap">
            {res.llm_string_preview}
          </pre>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Output Compression</h1>
        <p className="text-muted-foreground mt-1">
          Real measured compression using tiktoken + Aperture engine
        </p>
      </div>

      <div className="flex gap-2">
        {MODES.map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-2 rounded-md text-sm font-medium capitalize transition-colors ${
              mode === m ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {DATASET_TOOLS.map((ds) => (
          <Card key={ds.key}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">{ds.label}</CardTitle>
                <button
                  onClick={() => runDataset(ds.key, ds.tool_slug)}
                  disabled={loading === ds.key}
                  className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                  {loading === ds.key ? "Running..." : "Measure"}
                </button>
              </div>
            </CardHeader>
            <CardContent>{renderResult(ds.key, ds.label)}</CardContent>
          </Card>
        ))}
        {MOCK_TOOLS.map((tool) => (
          <Card key={tool.slug}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">{tool.label}</CardTitle>
                <button
                  onClick={() => runTool(tool.slug)}
                  disabled={loading === tool.slug}
                  className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                  {loading === tool.slug ? "Running..." : "Measure"}
                </button>
              </div>
            </CardHeader>
            <CardContent>{renderResult(tool.slug, tool.label)}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
