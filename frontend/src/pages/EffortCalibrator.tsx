import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import { Step } from "@/components/StepShell";
import { ComposingSpinner } from "@/components/ComposingSpinner";

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

interface LogEvent {
  ts: string;
  level: "info" | "trace" | "ok" | "warn";
  text: string;
}

function nowTime() {
  const d = new Date();
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${d.getMilliseconds().toString().padStart(3, "0").slice(0, 3)}`;
}

export default function EffortCalibrator() {
  const [tool, setTool] = useState(TOOLS[0]);
  const [ask, setAsk] = useState(PRESET_ASKS[0].ask);
  const [signalsInput, setSignalsInput] = useState(PRESET_ASKS[0].signals.join(", "));
  const [model, setModel] = useState("gpt-4o");
  const [result, setResult] = useState<CalibrateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<LogEvent[]>([]);

  const applyPreset = (idx: number) => {
    const preset = PRESET_ASKS[idx];
    setAsk(preset.ask);
    setSignalsInput(preset.signals.join(", "));
  };

  const pushLog = (event: LogEvent) => {
    setLog((prev) => [...prev, event]);
  };

  const run = async () => {
    setLoading(true);
    setResult(null);
    setLog([]);
    const required_signals = signalsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    pushLog({ ts: nowTime(), level: "info", text: `aperture.calibrate(${tool.slug})` });
    pushLog({ ts: nowTime(), level: "info", text: `  ask = "${ask.length > 60 ? ask.slice(0, 60) + '…' : ask}"` });
    pushLog({ ts: nowTime(), level: "info", text: `  required_signals = [${required_signals.join(", ")}]` });
    pushLog({ ts: nowTime(), level: "info", text: `  model = ${model}` });

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

    let res: CalibrateResponse | null = null;
    try {
      res = await apiPost("/api/effort/calibrate", payload);
    } catch (e) {
      pushLog({ ts: nowTime(), level: "warn", text: `error: ${(e as Error).message}` });
      setLoading(false);
      return;
    }
    if (!res) return;

    pushLog({ ts: nowTime(), level: "info", text: `→ classified difficulty: ${res.difficulty} (max=${res.max_aggression})` });
    for (const a of res.attempts) {
      const tag = a.passed ? "ok" : "trace";
      const detail = a.passed
        ? "all signals preserved"
        : `missing ${a.failed_signals.join(", ")}`;
      pushLog({
        ts: nowTime(),
        level: tag as LogEvent["level"],
        text: `  try ${a.mode.padEnd(11)} → ${a.tokens.toLocaleString().padStart(7)} tok · ${a.passed ? "✓" : "✗"} ${detail}`,
      });
    }
    pushLog({
      ts: nowTime(),
      level: "ok",
      text: `selected ${res.selected_mode} · ${res.selected_tokens.toLocaleString()} tok (saved ${res.saved_percent}%)`,
    });

    setResult(res);
    setLoading(false);
  };

  const stepStates = {
    one:   tool ? "complete" : "active",
    two:   ask.trim() ? "complete" : tool ? "active" : "pending",
    three: signalsInput.trim() ? "complete" : ask.trim() ? "active" : "pending",
    four:  result ? "complete" : signalsInput.trim() ? "active" : "pending",
  } as const;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          <span className="lime-dot" />
          Quality-gated auto effort
        </div>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Effort calibrator</h1>
        <p className="text-muted-foreground text-sm mt-2 max-w-3xl">
          Pick a tool, paste the user's ask, and list the signals the LLM's answer must still
          contain. Aperture classifies the ask, walks compression modes from cheapest to safest,
          and returns the first one that preserves every required signal.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 flex flex-col">
          {/* Step 1 — tool */}
          <Step index={1} title="Pick a Composio tool" state={stepStates.one}>
            <Card>
              <CardContent className="pt-5 pb-5">
                <div className="grid grid-cols-3 gap-2">
                  {TOOLS.map((t) => {
                    const active = t.slug === tool.slug;
                    return (
                      <button
                        key={t.slug}
                        type="button"
                        onClick={() => setTool(t)}
                        className={`flex flex-col items-start gap-1 px-3 py-2.5 rounded-md border text-left transition-colors ${
                          active
                            ? "border-primary/60 bg-primary/5 text-foreground"
                            : "border-border text-muted-foreground hover:border-primary/30 hover:text-foreground"
                        }`}
                      >
                        <span className="text-[12px] font-medium">{t.label}</span>
                        <span className="text-[10px] font-mono text-muted-foreground/80 truncate w-full">
                          {t.slug}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </Step>

          {/* Step 2 — ask */}
          <Step index={2} title="What is the user actually asking the agent to do?" state={stepStates.two}>
            <Card>
              <CardContent className="pt-5 pb-5 space-y-3">
                <textarea
                  value={ask}
                  onChange={(e) => setAsk(e.target.value)}
                  className="w-full min-h-[68px] px-3 py-2 rounded-md border bg-background text-sm font-sans"
                  placeholder="The agent's user prompt, in their own words…"
                />
                <div className="flex flex-wrap gap-1.5">
                  {PRESET_ASKS.map((p, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => applyPreset(i)}
                      className="text-[11px] px-2 py-0.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
                    >
                      {p.ask.slice(0, 38)}{p.ask.length > 38 ? "…" : ""}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </Step>

          {/* Step 3 — signals & model */}
          <Step index={3} title="Required signals + tokenizer" state={stepStates.three}>
            <Card>
              <CardContent className="pt-5 pb-5 space-y-3">
                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Required signals · substrings or dot-paths
                  </label>
                  <input
                    value={signalsInput}
                    onChange={(e) => setSignalsInput(e.target.value)}
                    className="w-full h-9 px-3 rounded-md border bg-background text-sm font-mono"
                    placeholder="title, assignee.login, OAuth"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Tokenizer (model)
                  </label>
                  <div className="relative">
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full h-9 px-3 rounded-md border bg-background text-sm appearance-none"
                    >
                      <option value="gpt-4o">gpt-4o · o200k_base</option>
                      <option value="gpt-4.1">gpt-4.1 · o200k_base</option>
                      <option value="claude-opus-4-7">claude-opus-4-7 · cl100k approx</option>
                      <option value="claude-sonnet-4-6">claude-sonnet-4-6 · cl100k approx</option>
                      <option value="claude-haiku-4-5">claude-haiku-4-5 · cl100k approx</option>
                      <option value="gemini-2.5-pro">gemini-2.5-pro · cl100k approx</option>
                    </select>
                    <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </Step>

          {/* Step 4 — run */}
          <Step index={4} title="Run the calibration" state={stepStates.four}>
            <Card>
              <CardContent className="pt-5 pb-5 space-y-4">
                <div className="flex items-center gap-3">
                  <Button
                    onClick={run}
                    disabled={loading}
                    className="bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    {loading ? "Calibrating…" : "Calibrate effort"}
                  </Button>
                  {loading && <ComposingSpinner />}
                </div>

                {result && (
                  <div className="grid grid-cols-4 gap-3">
                    <div className="border border-border rounded-md p-3">
                      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Difficulty</p>
                      <p className="text-lg font-semibold capitalize mt-0.5">{result.difficulty}</p>
                      <p className="text-[10px] text-muted-foreground">max: {result.max_aggression}</p>
                    </div>
                    <div className="border border-border rounded-md p-3">
                      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Selected</p>
                      <p className="text-lg font-semibold text-primary capitalize mt-0.5">{result.selected_mode}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {result.selected_mode === "off" ? "raw passthrough" : "all signals ✓"}
                      </p>
                    </div>
                    <div className="border border-border rounded-md p-3">
                      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Tokens</p>
                      <p className="text-lg font-semibold metric-value mt-0.5">{result.selected_tokens.toLocaleString()}</p>
                      <p className="text-[10px] text-muted-foreground metric-value">was {result.raw_tokens.toLocaleString()}</p>
                    </div>
                    <div className="border border-primary/40 rounded-md p-3">
                      <p className="text-[10px] uppercase tracking-[0.14em] text-primary">Saved</p>
                      <p className="text-lg font-semibold text-primary metric-value mt-0.5">{result.saved_percent}%</p>
                      <p className="text-[10px] text-muted-foreground metric-value">−{result.saved_tokens.toLocaleString()} tok</p>
                    </div>
                  </div>
                )}

                {result && (
                  <div className="space-y-1">
                    <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-1">Per-mode trace</p>
                    {result.attempts.map((a) => {
                      const isSelected = a.mode === result.selected_mode;
                      return (
                        <div
                          key={a.mode}
                          className={`flex items-center gap-3 px-3 py-1.5 rounded-md border text-[12px] ${
                            isSelected ? "border-primary/60 bg-primary/5" : "border-border"
                          }`}
                        >
                          <span className={`w-1 h-3.5 rounded-full ${isSelected ? "bg-primary" : "bg-transparent"}`} />
                          <Badge variant={a.passed ? "default" : "secondary"} className="capitalize w-20 justify-center">
                            {a.mode}
                          </Badge>
                          <span className="metric-value w-20 text-right text-muted-foreground">
                            {a.tokens.toLocaleString()}
                          </span>
                          {a.passed ? (
                            <span className="text-muted-foreground">✓ all signals preserved</span>
                          ) : (
                            <span className="text-muted-foreground">
                              ✗ missing <span className="font-mono text-foreground/80">{a.failed_signals.join(", ")}</span>
                            </span>
                          )}
                          {isSelected && <span className="ml-auto text-[10px] uppercase tracking-[0.14em] text-primary">selected</span>}
                        </div>
                      );
                    })}
                  </div>
                )}

                {result && (
                  <p className="text-[12px] text-muted-foreground">{result.reason}</p>
                )}
              </CardContent>
            </Card>
          </Step>
        </div>

        {/* Live execution log */}
        <div className="col-span-1">
          <div className="sticky top-16 rounded-xl border border-border overflow-hidden bg-[#0A0A0A]">
            <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-black/40">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                Execution log
              </p>
              {loading && <ComposingSpinner label="streaming" />}
            </div>
            <div className="p-3 text-[11px] font-mono leading-[1.55] min-h-[420px] max-h-[560px] overflow-auto">
              {log.length === 0 && !loading && (
                <p className="text-muted-foreground/60">
                  &gt; waiting for your calibration <span className="aperture-pulse">▌</span>
                </p>
              )}
              {log.map((event, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-muted-foreground/60 select-none">{event.ts}</span>
                  <span
                    className={
                      event.level === "ok"
                        ? "text-primary"
                        : event.level === "warn"
                          ? "text-rose-400"
                          : event.level === "trace"
                            ? "text-foreground/70"
                            : "text-foreground/85"
                    }
                  >
                    {event.text}
                  </span>
                </div>
              ))}
              {loading && (
                <div className="flex gap-2">
                  <span className="text-primary aperture-pulse">▌</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
