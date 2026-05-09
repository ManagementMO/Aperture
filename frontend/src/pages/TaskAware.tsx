import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import ResultSkeleton from "@/components/ResultSkeleton";

interface TaskProfile {
  task_name: string;
  tool_slug: string;
  required_fields: string[];
  description: string;
}

interface CompressionMeasurement {
  raw_tokens: number;
  compressed_tokens: number;
  tokens_saved: number;
  compression_ratio: number;
  strategy: string;
  mode: string;
  tool_slug: string;
  task: string | null;
  protected_field_count: number;
  omitted_fields: string[];
}

interface TaskAwareResponse {
  baseline: CompressionMeasurement;
  task_aware: CompressionMeasurement;
  profile: TaskProfile | null;
  delta_tokens_saved: number;
  quality_preservation: string;
}

const DATASETS = [
  { key: "notion_pages", label: "Notion Pages", tool: "NOTION_SEARCH_NOTION_PAGE" },
  { key: "linear_issues", label: "Linear Issues", tool: "LINEAR_GET_LINEAR_USER_ISSUES" },
  { key: "supabase_users", label: "Supabase Users", tool: "SUPABASE_FETCH_TABLE_ROWS" },
] as const;

const MODES = ["safe", "balanced", "low"] as const;

function describeTradeoff(delta: number): { label: string; detail: string } {
  if (delta > 0) {
    return {
      label: `${delta.toLocaleString()} more saved`,
      detail: "Task-aware dropped extra non-essential fields the LLM doesn't need for this task.",
    };
  }
  if (delta < 0) {
    return {
      label: `${Math.abs(delta).toLocaleString()} fewer saved`,
      detail: "Task-aware kept additional fields required by this task — fewer tokens saved, higher answer quality.",
    };
  }
  return {
    label: "no change",
    detail: "Both passes ended at the same compressed size — protected fields are already in the baseline shape.",
  };
}

export default function TaskAware() {
  const [profiles, setProfiles] = useState<TaskProfile[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<typeof DATASETS[number]["key"]>(DATASETS[0].key);
  const [selectedMode, setSelectedMode] = useState<(typeof MODES)[number]>("balanced");
  const [selectedTask, setSelectedTask] = useState("");
  const [result, setResult] = useState<TaskAwareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const dataset = DATASETS.find((d) => d.key === selectedDataset);

  useEffect(() => {
    if (!dataset) return;
    apiGet(`/api/task-profiles?tool_slug=${dataset.tool}`).then((res) => {
      const list: TaskProfile[] = res.profiles ?? [];
      setProfiles(list);
      setSelectedTask(list[0]?.task_name ?? "");
    });
  }, [selectedDataset]);

  const run = async () => {
    if (!dataset || !selectedTask) return;
    setLoading(true);
    setResult(null);
    const res = await apiPost("/api/compress/task-aware", {
      dataset: selectedDataset,
      tool_slug: dataset.tool,
      mode: selectedMode,
      task: selectedTask,
    });
    setResult(res);
    setLoading(false);
  };

  const tradeoff = result ? describeTradeoff(result.delta_tokens_saved) : null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Task-Aware Compression</h1>
        <p className="text-muted-foreground mt-1">
          Phase 1: Preserve quality by keeping only fields the LLM needs for the current task.
          Protected fields are retained; everything else gets aggressively compressed.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4 flex-wrap">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Dataset</label>
            <div className="relative">
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value as typeof DATASETS[number]["key"])}
                className="w-48 h-9 px-3 rounded-md border bg-background text-sm appearance-none"
              >
                {DATASETS.map((d) => (
                  <option key={d.key} value={d.key}>{d.label}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Mode</label>
            <div className="relative">
              <select
                value={selectedMode}
                onChange={(e) => setSelectedMode(e.target.value as (typeof MODES)[number])}
                className="w-32 h-9 px-3 rounded-md border bg-background text-sm appearance-none"
              >
                {MODES.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Task Profile</label>
            <div className="relative">
              <select
                value={selectedTask}
                onChange={(e) => setSelectedTask(e.target.value)}
                className="w-64 h-9 px-3 rounded-md border bg-background text-sm appearance-none"
              >
                {profiles.map((p) => (
                  <option key={p.task_name} value={p.task_name}>{p.task_name}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
            </div>
          </div>

          <div className="flex items-end">
            <Button onClick={run} disabled={loading || !selectedTask}>
              {loading ? "Running..." : "Compare"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && <ResultSkeleton cards={3} />}

      {!loading && result && tradeoff && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Baseline ({selectedMode})</p>
                <p className="text-2xl font-semibold text-rose-600">
                  {result.baseline.raw_tokens.toLocaleString()}
                  <span className="text-sm text-muted-foreground font-normal"> → </span>
                  {result.baseline.compressed_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  Saved {result.baseline.tokens_saved.toLocaleString()} tokens
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Task-Aware ({selectedTask})</p>
                <p className="text-2xl font-semibold text-emerald-600">
                  {result.task_aware.raw_tokens.toLocaleString()}
                  <span className="text-sm text-muted-foreground font-normal"> → </span>
                  {result.task_aware.compressed_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  Saved {result.task_aware.tokens_saved.toLocaleString()} tokens
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Quality Tradeoff</p>
                <p className="text-2xl font-semibold text-blue-600">{tradeoff.label}</p>
                <p className="text-xs text-muted-foreground mt-1">{tradeoff.detail}</p>
              </CardContent>
            </Card>
          </div>

          {result.profile && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Active Profile: {result.profile.task_name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{result.profile.description}</p>
                <div>
                  <p className="text-xs font-medium mb-2">
                    Protected Fields ({result.profile.required_fields.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {result.profile.required_fields.map((f) => (
                      <Badge key={f} variant="default" className="text-xs">{f}</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium mb-2">Aggressively Compressed Fields (sample)</p>
                  <div className="flex flex-wrap gap-1">
                    {(result.baseline.omitted_fields ?? []).slice(0, 20).map((f) => (
                      <Badge key={f} variant="secondary" className="text-xs">{f}</Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
