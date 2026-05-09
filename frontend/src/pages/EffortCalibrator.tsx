import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, Sparkles } from "lucide-react";
import ResultSkeleton from "@/components/ResultSkeleton";

const TOOLS = [
  { slug: "GITHUB_LIST_ISSUES", label: "GitHub Issues", args: { per_page: 5 } },
  { slug: "GITHUB_GET_A_REPOSITORY", label: "GitHub Repo", args: {} },
  { slug: "GMAIL_SEARCH_EMAILS", label: "Gmail Search", args: { query: "bug", max_results: 3 } },
  { slug: "SLACK_SEARCH_MESSAGES", label: "Slack Messages", args: { query: "bug", count: 4 } },
  { slug: "NOTION_SEARCH_NOTION_PAGE", label: "Notion (500 pages)", args: {}, dataset: "notion_pages" },
  { slug: "LINEAR_GET_LINEAR_USER_ISSUES", label: "Linear (200 issues)", args: {}, dataset: "linear_issues" },
];

const PRESET_ASKS = [
  { ask: "Who's assigned to which open issue?", signals: ["title", "assignee.login"] },
  { ask: "What's the OAuth bug about?", signals: ["title", "OAuth", "body"] },
  { ask: "Summarize the top 3 customer emails", signals: ["subject", "from", "snippet"] },
  { ask: "Analyze the priority and severity of every issue and recommend triage", signals: ["title", "labels", "body"] },
];

interface ModeAttempt {
  mode: string;
  tokens: number;
  passed: boolean;
  failed_signals: string[];
}

interface CalibrateResponse {
  tool_slug: string;
  ask: string;
  required_signals: string[];
  difficulty: string;
  max_aggression: string;
  selected_mode: string;
  selected_tokens: number;
  raw_tokens: number;
  saved_tokens: number;
  saved_percent: number;
  attempts: ModeAttempt[];
  reason: string;
}

export default function EffortCalibrator() {
  const [tool, setTool] = useState(TOOLS[0]);
  const [ask, setAsk] = useState(PRESET_ASKS[0].ask);
  const [signalsInput, setSignalsInput] = useState(PRESET_ASKS[0].signals.join(", "));
  const [model, setModel] = useState("gpt-4o");
  const [result, setResult] = useState<CalibrateResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const applyPreset = (idx: number) => {
    const preset = PRESET_ASKS[idx];
    setAsk(preset.ask);
    setSignalsInput(preset.signals.join(", "));
  };

  const run = async () => {
    setLoading(true);
    setResult(null);
    const required_signals = signalsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const payload: Record<string, unknown> = {
      tool_slug: tool.slug,
      arguments: tool.args,
      ask,
      required_signals,
      model,
    };
    if ((tool as { dataset?: string }).dataset) {
      payload.dataset = (tool as { dataset?: string }).dataset;
    }

    const res = await apiPost("/api/effort/calibrate", payload);
    setResult(res);
    setLoading(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          <Sparkles className="w-3 h-3 text-primary" />
          Quality-gated auto effort
        </div>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Effort calibrator</h1>
        <p className="text-muted-foreground text-sm mt-2 max-w-3xl">
          Pick a tool, paste the user's ask, and list the signals the LLM's answer must still
          contain. Aperture classifies the ask, picks a mode floor by difficulty, then walks
          modes from cheapest to safest and returns the most aggressive one that preserves
          every required signal.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Calibration input</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
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
              <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Model (tokenizer)</label>
              <div className="relative">
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full h-9 px-3 rounded-md border bg-background text-sm appearance-none"
                >
                  <option value="gpt-4o">gpt-4o (o200k_base)</option>
                  <option value="gpt-4.1">gpt-4.1 (o200k_base)</option>
                  <option value="claude-opus-4-7">claude-opus-4-7 (cl100k approx)</option>
                  <option value="claude-sonnet-4-6">claude-sonnet-4-6 (cl100k approx)</option>
                  <option value="claude-haiku-4-5">claude-haiku-4-5 (cl100k approx)</option>
                  <option value="gemini-2.5-pro">gemini-2.5-pro (cl100k approx)</option>
                </select>
                <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
              </div>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">User ask</label>
            <textarea
              value={ask}
              onChange={(e) => setAsk(e.target.value)}
              className="w-full min-h-[60px] px-3 py-2 rounded-md border bg-background text-sm font-sans"
              placeholder="What is the user actually asking the agent to do?"
            />
            <div className="flex flex-wrap gap-1.5 pt-1">
              {PRESET_ASKS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => applyPreset(i)}
                  className="text-[11px] px-2 py-0.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
                >
                  {p.ask.slice(0, 38)}{p.ask.length > 38 ? "…" : ""}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
              Required signals (comma-separated; substrings or dot-paths)
            </label>
            <input
              value={signalsInput}
              onChange={(e) => setSignalsInput(e.target.value)}
              className="w-full h-9 px-3 rounded-md border bg-background text-sm font-mono"
              placeholder="title, assignee.login, OAuth"
            />
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={run} disabled={loading} className="bg-primary text-primary-foreground hover:bg-primary/90">
              {loading ? "Calibrating..." : "Calibrate effort"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Aperture will try modes cheapest-first and return the one that preserves every
              signal.
            </p>
          </div>
        </CardContent>
      </Card>

      {loading && <ResultSkeleton cards={3} />}

      {!loading && result && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-3">
            <Card>
              <CardContent className="pt-5 space-y-1">
                <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Difficulty</p>
                <p className="text-2xl font-semibold capitalize">{result.difficulty}</p>
                <p className="text-xs text-muted-foreground">max aggression: {result.max_aggression}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-5 space-y-1">
                <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Selected mode</p>
                <p className="text-2xl font-semibold text-primary capitalize">{result.selected_mode}</p>
                <p className="text-xs text-muted-foreground">
                  {result.selected_mode === "off"
                    ? "raw passthrough"
                    : "preserves every signal"}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-5 space-y-1">
                <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Tokens</p>
                <p className="text-2xl font-semibold metric-value">
                  {result.selected_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground metric-value">
                  was {result.raw_tokens.toLocaleString()}
                </p>
              </CardContent>
            </Card>
            <Card className="border-primary/40">
              <CardContent className="pt-5 space-y-1">
                <p className="text-[11px] uppercase tracking-[0.14em] text-primary">Saved</p>
                <p className="text-2xl font-semibold text-primary metric-value">
                  {result.saved_percent}%
                </p>
                <p className="text-xs text-muted-foreground metric-value">
                  −{result.saved_tokens.toLocaleString()} tokens
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Per-mode trace</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {result.attempts.map((a) => {
                  const isSelected = a.mode === result.selected_mode;
                  return (
                    <div
                      key={a.mode}
                      className={`flex items-center gap-3 px-3 py-2 rounded-md border text-sm ${
                        isSelected
                          ? "border-primary/60 bg-primary/5"
                          : a.passed
                            ? "border-border"
                            : "border-border/60 bg-muted/30"
                      }`}
                    >
                      <span className="w-1 h-4 rounded-full" style={{ background: isSelected ? "var(--primary)" : "transparent" }} />
                      <Badge variant={a.passed ? "default" : "secondary"} className="capitalize w-20 justify-center">
                        {a.mode}
                      </Badge>
                      <span className="metric-value w-20 text-right text-muted-foreground">
                        {a.tokens.toLocaleString()}
                      </span>
                      {a.passed ? (
                        <span className="text-[12px] text-muted-foreground">✓ all signals preserved</span>
                      ) : (
                        <span className="text-[12px] text-muted-foreground">
                          ✗ missing: <span className="font-mono text-foreground/80">{a.failed_signals.join(", ")}</span>
                        </span>
                      )}
                      {isSelected && (
                        <span className="ml-auto text-[10px] uppercase tracking-[0.14em] text-primary">selected</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground mb-1">Reason</p>
              <p className="text-sm">{result.reason}</p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
