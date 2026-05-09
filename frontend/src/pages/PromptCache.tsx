import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import ResultSkeleton from "@/components/ResultSkeleton";

const PROVIDERS = [
  { key: "anthropic", label: "Anthropic", discount: "90%" },
  { key: "openai", label: "OpenAI", discount: "50%" },
  { key: "generic", label: "Generic", discount: "75%" },
];

const SAMPLE = {
  system_prompt:
    "You are a helpful coding assistant. You have access to GitHub, Notion, Linear, and Slack tools. Always think step by step before taking action. " +
    "Prefer narrow tool calls over broad ones. When you need to inspect a file, fetch it once and reuse it across the conversation rather than re-fetching. " +
    "Treat tool results as authoritative — do not contradict them in summaries.",
  tool_schemas: [
    'GITHUB_LIST_ISSUES(string:owner,repo,state<open|closed|all>?,labels?,assignee?;int:per_page?,page?;bool:archived?)',
    'NOTION_SEARCH_NOTION_PAGE(string:query,sort<last_edited_time|created_time>?;int:page_size?;bool:include_archived?;obj:filter?)',
    'GMAIL_SEARCH_EMAILS(string:query;int:max_results?;bool:include_spam_trash?)',
    'SLACK_SEARCH_MESSAGES(string:query;int:count?,page?)',
  ],
  static_context: [
    "Project: Aperture — Tool Context Control Plane. Tech stack: Python 3.11, FastAPI, React, TypeScript, Vite, Tailwind, shadcn/ui.\n" +
      "Goals: cut Composio token bloat without losing answer quality. Sprint focus: prompt caching (this page), TOON encoding, type-grouped schemas.",
  ],
  tool_results: [
    '{"_aperture_ref":"abc123","_aperture_summary":{"count":47,"states":{"open":3,"closed":44}}}',
  ],
  user_messages: ["Find all high-priority open bugs in the composio repo and summarize the top 3."],
};

interface BlockReport {
  type: string;
  cacheable: boolean;
  estimated_tokens: number;
  content_preview: string;
}

interface BreakpointReport {
  index: number;
  ttl: string;
  reason: string;
}

interface SavingsReport {
  total_tokens: number;
  cacheable_tokens: number;
  cacheable_1h_tokens: number;
  cacheable_5m_tokens: number;
  dynamic_tokens: number;
  skipped_below_threshold: number;
  min_cacheable_tokens: number;
  expected_turns: number;
  first_call_cost: number;
  warm_call_cost: number;
  naive_cost: number;
  amortized_cost: number;
  tokens_saved: number;
  savings_percent: number;
  provider: string;
  breakpoints: BreakpointReport[];
}

interface OptimizeResponse {
  blocks: BlockReport[];
  ordering: string;
  provider: string;
  estimated_savings: SavingsReport;
  recommendation: string;
}

export default function PromptCache() {
  const [provider, setProvider] = useState("anthropic");
  const [historyTurns, setHistoryTurns] = useState(8);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setResult(null);
    const res = await apiPost("/api/prompt-cache/optimize", {
      ...SAMPLE,
      provider,
      history_turn_count: historyTurns,
    });
    setResult(res);
    setLoading(false);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Prompt Caching</h1>
        <p className="text-muted-foreground mt-1">
          Phase 3: Reorder prompts so stable content (system, tool schemas, static context)
          gets dedicated <code className="px-1.5 py-0.5 bg-muted rounded">cache_control</code> breakpoints.
          Anthropic supports up to 4 — we use them across two TTL tiers (1h for stable, 5m for rolling).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4 flex-wrap items-end">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Provider</label>
            <div className="relative">
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-40 h-9 px-3 rounded-md border bg-background text-sm appearance-none"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.key} value={p.key}>{p.label}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">History turns</label>
            <input
              type="number"
              min={0}
              max={50}
              value={historyTurns}
              onChange={(e) => setHistoryTurns(Number(e.target.value))}
              className="w-24 h-9 px-3 rounded-md border bg-background text-sm"
            />
          </div>

          <Button onClick={run} disabled={loading}>
            {loading ? "Optimizing..." : "Build Optimized Prompt"}
          </Button>
        </CardContent>
      </Card>

      {loading && <ResultSkeleton cards={4} />}

      {!loading && result && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Total Tokens</p>
                <p className="text-2xl font-semibold">{result.estimated_savings.total_tokens.toLocaleString()}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Cacheable</p>
                <p className="text-2xl font-semibold text-emerald-600">
                  {result.estimated_savings.cacheable_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  1h: {result.estimated_savings.cacheable_1h_tokens.toLocaleString()} · 5m: {result.estimated_savings.cacheable_5m_tokens.toLocaleString()}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Dynamic</p>
                <p className="text-2xl font-semibold text-amber-600">
                  {result.estimated_savings.dynamic_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">never cached</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Amortized Savings</p>
                <p className="text-2xl font-semibold text-blue-600">
                  {result.estimated_savings.savings_percent}%
                </p>
                <p className="text-xs text-muted-foreground">
                  over {result.estimated_savings.expected_turns} turns
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Naive cost</p>
                <p className="text-xl font-semibold">{result.estimated_savings.naive_cost.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">no caching</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">First call (cold)</p>
                <p className="text-xl font-semibold text-amber-600">{result.estimated_savings.first_call_cost.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">includes write multipliers</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Warm call</p>
                <p className="text-xl font-semibold text-emerald-600">{result.estimated_savings.warm_call_cost.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">cache reads + dynamic</p>
              </CardContent>
            </Card>
          </div>

          {result.estimated_savings.skipped_below_threshold > 0 && (
            <Card className="border-amber-500/40">
              <CardContent className="pt-4 pb-4 flex items-center justify-between">
                <p className="text-sm text-amber-600">
                  {result.estimated_savings.skipped_below_threshold.toLocaleString()} tokens fall below the {result.estimated_savings.min_cacheable_tokens}-token minimum and won't actually cache.
                </p>
                <Badge variant="outline">{provider} threshold</Badge>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">
                Breakpoints ({result.estimated_savings.breakpoints.length} of 4 max)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {result.estimated_savings.breakpoints.map((bp, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <Badge variant="default" className="font-mono">#{i + 1}</Badge>
                  <Badge variant={bp.ttl === "1h" ? "secondary" : "outline"}>{bp.ttl}</Badge>
                  <span className="text-muted-foreground">at block {bp.index}</span>
                  <span>·</span>
                  <span>{bp.reason}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Block Order (stable → dynamic)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {result.blocks.map((block, i) => {
                const breakpoint = result.estimated_savings.breakpoints.find((bp) => bp.index === i);
                return (
                  <div
                    key={i}
                    className={`flex items-center gap-3 p-3 rounded-md border ${
                      block.cacheable ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
                    }`}
                  >
                    <div className="text-xs font-mono w-6 text-center text-muted-foreground">{i + 1}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium capitalize">{block.type.replace("_", " ")}</span>
                        <Badge variant={block.cacheable ? "default" : "secondary"} className="text-xs">
                          {block.cacheable ? "cacheable" : "dynamic"}
                        </Badge>
                        {breakpoint && (
                          <Badge variant="outline" className="text-xs">
                            ↳ cache_control {breakpoint.ttl}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{block.estimated_tokens.toLocaleString()} tokens</p>
                    </div>
                    <div className="text-xs text-muted-foreground max-w-xs truncate">
                      {block.content_preview}
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
