import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import ResultSkeleton from "@/components/ResultSkeleton";

const TOOLS = [
  { slug: "GITHUB_LIST_ISSUES", label: "GitHub Issues", args: { per_page: 5 } },
  { slug: "GITHUB_GET_A_REPOSITORY", label: "GitHub Repo", args: {} },
  { slug: "GITHUB_LIST_PULL_REQUESTS", label: "GitHub PRs", args: { per_page: 3 } },
  { slug: "GMAIL_SEARCH_EMAILS", label: "Gmail Search", args: { query: "bug", max_results: 3 } },
  { slug: "SLACK_SEARCH_MESSAGES", label: "Slack Messages", args: { query: "bug", count: 4 } },
];

const PRESETS = [
  { ask: "show me the avatar of every assignee", expects: "avatar_url, gravatar_id" },
  { ask: "clone each open PR's branch with git", expects: "clone_url, ssh_url" },
  { ask: "summarize the open issues by title and state", expects: "(no promotions needed)" },
  { ask: "look up the GraphQL node_id for each issue", expects: "node_id" },
];

interface RunSummary {
  raw_tokens: number;
  compressed_tokens: number;
  policy_mode: string;
  policy_reason_counts: Record<string, number>;
  policy_promotions: { name: string; path: string; reason: string }[];
  classifier_used: boolean;
  classifier_keeps: string[];
  classifier_cost_usd: number;
}

interface ExplainResponse {
  tool_slug: string;
  ask: string;
  mode: string;
  runs: Record<"static" | "ask_aware" | "model_assisted", RunSummary>;
  classifier_health: {
    selected_provider: string;
    huggingface_available: boolean;
    anthropic_available: boolean;
    hf_default_model: string;
    anthropic_default_model: string;
    cache_entries: number;
  };
}

const REASON_COLORS: Record<string, string> = {
  explicit: "bg-primary/15 text-primary border-primary/30",
  explicit_descendant: "bg-primary/10 text-primary border-primary/20",
  ask: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  model: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  default: "bg-muted text-muted-foreground border-border",
  denial_list: "bg-rose-500/10 text-rose-300 border-rose-500/30",
};

function ReasonBadge({ reason, count }: { reason: string; count: number }) {
  const cls = REASON_COLORS[reason] ?? REASON_COLORS.default;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border text-[11px] font-mono ${cls}`}>
      {reason} <span className="metric-value">{count}</span>
    </span>
  );
}

function RunCard({ title, subtitle, run, isWinner }: { title: string; subtitle: string; run: RunSummary; isWinner: boolean }) {
  const savings = run.raw_tokens > 0 ? Math.round((1 - run.compressed_tokens / run.raw_tokens) * 100) : 0;
  return (
    <div className={`rounded-md border p-4 space-y-3 ${isWinner ? "border-primary/50 bg-primary/5" : "border-border"}`}>
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{title}</p>
          <p className="text-[10px] text-muted-foreground/80 mt-0.5">{subtitle}</p>
        </div>
        {isWinner && <span className="text-[10px] uppercase tracking-[0.14em] text-primary">smartest</span>}
      </div>
      <div>
        <p className="text-2xl font-semibold metric-value">
          {run.compressed_tokens.toLocaleString()}
          <span className="text-[12px] text-muted-foreground font-normal"> / {run.raw_tokens.toLocaleString()}</span>
        </p>
        <p className="text-[11px] text-muted-foreground metric-value">{savings}% saved</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {Object.entries(run.policy_reason_counts).map(([reason, count]) => (
          <ReasonBadge key={reason} reason={reason} count={count} />
        ))}
      </div>
      {run.policy_promotions.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Promoted back to keep</p>
          <div className="flex flex-wrap gap-1">
            {run.policy_promotions.slice(0, 12).map((p, i) => (
              <span key={i} className="px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] font-mono">
                {p.path} <span className="text-muted-foreground/70">· {p.reason}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      {run.classifier_used && (
        <p className="text-[10px] text-muted-foreground">
          classifier promoted <span className="font-mono">{run.classifier_keeps.join(", ") || "—"}</span>
          {run.classifier_cost_usd > 0 && <> · ${run.classifier_cost_usd.toFixed(6)}</>}
        </p>
      )}
    </div>
  );
}

export default function FieldPolicy() {
  const [tool, setTool] = useState(TOOLS[0]);
  const [ask, setAsk] = useState(PRESETS[0].ask);
  const [mode, setMode] = useState("balanced");
  const [result, setResult] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<ExplainResponse["classifier_health"] | null>(null);

  useEffect(() => {
    apiGet("/api/field-policy/health").then(setHealth);
  }, []);

  const run = async () => {
    setLoading(true);
    setResult(null);
    const payload: Record<string, unknown> = {
      tool_slug: tool.slug,
      arguments: tool.args,
      ask,
      mode,
    };
    const res: ExplainResponse = await apiPost("/api/field-policy/explain", payload);
    setResult(res);
    setLoading(false);
  };

  const winner: keyof ExplainResponse["runs"] | null = result
    ? (Object.entries(result.runs).reduce((best, [name, r]) =>
        r.compressed_tokens < (result.runs[best].compressed_tokens ?? Infinity) ? (name as keyof ExplainResponse["runs"]) : best,
        "static" as keyof ExplainResponse["runs"],
      ))
    : null;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          <span className="lime-dot" />
          Smart field policy
        </div>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Field policy</h1>
        <p className="text-muted-foreground text-sm mt-2 max-w-3xl">
          Replaces the static denial list with a layered, ask-aware decision per field.
          Three tiers, cheapest first: <span className="font-mono">explicit signals</span> → <span className="font-mono">user-ask mention</span> →
          <span className="font-mono"> small-model classifier</span> → static denial list. The model is asymmetric — it can only
          rescue a denied field, never demote a default-keep one.
        </p>
      </div>

      {health && (
        <Card>
          <CardContent className="pt-4 pb-4 flex items-center gap-3 flex-wrap text-[12px]">
            <Badge variant="secondary" className="font-mono">provider: {health.selected_provider}</Badge>
            <span className="text-muted-foreground">
              huggingface · {health.hf_default_model}
              <span className={health.huggingface_available ? "text-primary ml-1" : "text-rose-400 ml-1"}>
                {health.huggingface_available ? "online" : "no HF_API_TOKEN"}
              </span>
            </span>
            <span className="text-muted-foreground">
              anthropic · {health.anthropic_default_model}
              <span className={health.anthropic_available ? "text-primary ml-1" : "text-rose-400 ml-1"}>
                {health.anthropic_available ? "online" : "no ANTHROPIC_API_KEY"}
              </span>
            </span>
            <span className="text-muted-foreground ml-auto">cache: {health.cache_entries} entries</span>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Tool</label>
              <div className="relative">
                <select
                  value={tool.slug}
                  onChange={(e) => setTool(TOOLS.find((t) => t.slug === e.target.value) ?? TOOLS[0])}
                  className="w-full h-9 px-3 rounded-md border bg-background text-sm appearance-none"
                >
                  {TOOLS.map((t) => (
                    <option key={t.slug} value={t.slug}>{t.label}</option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Mode</label>
              <div className="relative">
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="w-full h-9 px-3 rounded-md border bg-background text-sm appearance-none"
                >
                  {["safe", "balanced", "low", "aggressive"].map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
              </div>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Agent ask</label>
            <textarea
              value={ask}
              onChange={(e) => setAsk(e.target.value)}
              className="w-full min-h-[64px] px-3 py-2 rounded-md border bg-background text-sm font-sans"
              placeholder="The agent's task in their own words…"
            />
            <div className="flex flex-wrap gap-1.5 pt-1">
              {PRESETS.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setAsk(p.ask)}
                  className="text-[11px] px-2 py-0.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
                  title={`expected promotions: ${p.expects}`}
                >
                  {p.ask}
                </button>
              ))}
            </div>
          </div>
          <Button onClick={run} disabled={loading} className="bg-primary text-primary-foreground hover:bg-primary/90">
            {loading ? "Running 3 passes…" : "Compare static / ask / model"}
          </Button>
        </CardContent>
      </Card>

      {loading && <ResultSkeleton cards={3} />}

      {!loading && result && (
        <div className="grid grid-cols-3 gap-3">
          <RunCard
            title="Static denial list"
            subtitle="how the engine used to behave — blunt drop"
            run={result.runs.static}
            isWinner={winner === "static"}
          />
          <RunCard
            title="Ask-aware"
            subtitle="word-bounded match against the ask · free"
            run={result.runs.ask_aware}
            isWinner={winner === "ask_aware"}
          />
          <RunCard
            title="Model-assisted"
            subtitle={`Gemma / Haiku classifier · cached per (tool, ask)`}
            run={result.runs.model_assisted}
            isWinner={winner === "model_assisted"}
          />
        </div>
      )}
    </div>
  );
}
