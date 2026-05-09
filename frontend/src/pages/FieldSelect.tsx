import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import ResultSkeleton from "@/components/ResultSkeleton";

const DATASETS = [
  { key: "notion_pages", label: "Notion Pages", tool: "NOTION_SEARCH_NOTION_PAGE" },
  { key: "linear_issues", label: "Linear Issues", tool: "LINEAR_GET_LINEAR_USER_ISSUES" },
  { key: "supabase_users", label: "Supabase Users", tool: "SUPABASE_FETCH_TABLE_ROWS" },
];

const MODES = ["safe", "balanced", "low"];

export default function FieldSelect() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState(DATASETS[0].key);
  const [selectedMode, setSelectedMode] = useState("balanced");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const dataset = DATASETS.find((d) => d.key === selectedDataset);

  useEffect(() => {
    if (dataset) {
      apiGet(`/api/field-profiles?tool_slug=${dataset.tool}`).then((res) => {
        setProfiles(res.profiles || []);
        if (res.profiles?.length > 0) {
          setSelectedProfile(res.profiles[0].profile_name);
        }
      });
    }
  }, [selectedDataset]);

  const run = async () => {
    if (!dataset || !selectedProfile) return;
    setLoading(true);
    const res = await apiPost("/api/compress/field-select", {
      dataset: selectedDataset,
      tool_slug: dataset.tool,
      mode: selectedMode,
      field_profile: selectedProfile,
    });
    setResult(res);
    setLoading(false);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Upstream Field Selection</h1>
        <p className="text-muted-foreground mt-1">
          Phase 4: Instead of fetching everything and then compressing, request only the fields
          you need from the API. This is lossless compression at the source — the data you don't
          need never enters the context window.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4 flex-wrap items-end">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Dataset</label>
            <div className="relative">
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
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
                onChange={(e) => setSelectedMode(e.target.value)}
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
            <label className="text-xs text-muted-foreground">Field Profile</label>
            <div className="relative">
              <select
                value={selectedProfile}
                onChange={(e) => setSelectedProfile(e.target.value)}
                className="w-48 h-9 px-3 rounded-md border bg-background text-sm appearance-none"
              >
                {profiles.map((p: any) => (
                  <option key={p.profile_name} value={p.profile_name}>{p.profile_name}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 absolute right-2 top-2.5 pointer-events-none text-muted-foreground" />
            </div>
          </div>

          <Button onClick={run} disabled={loading}>
            {loading ? "Running..." : "Compare"}
          </Button>
        </CardContent>
      </Card>

      {loading && <ResultSkeleton cards={3} />}

      {!loading && result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Baseline (all fields)</p>
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
                <p className="text-sm text-muted-foreground">Field-Selected</p>
                <p className="text-2xl font-semibold text-emerald-600">
                  {result.field_selected.raw_tokens.toLocaleString()}
                  <span className="text-sm text-muted-foreground font-normal"> → </span>
                  {result.field_selected.compressed_tokens.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  Saved {result.field_selected.tokens_saved.toLocaleString()} tokens
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Additional Savings</p>
                <p className="text-2xl font-semibold text-blue-600">
                  {result.delta_tokens_saved.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  vs baseline compression
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Fields Requested from API</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {result.fields_applied.map((f: string) => (
                  <Badge key={f} variant="outline" className="text-xs font-mono">
                    {f}
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                {result.quality_note}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
