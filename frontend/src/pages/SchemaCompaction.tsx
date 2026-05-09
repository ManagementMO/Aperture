import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SchemaSample {
  name: string;
  compact: string;
  json_tokens: number;
  compact_tokens: number;
  saved: number;
  savings_percent: number;
}

const EFFORT_MODES = [
  { mode: "low", tools_exposed: 5, fields_shown: "Required only", descriptions: "Short", examples: "None" },
  { mode: "medium", tools_exposed: 12, fields_shown: "Required + common", descriptions: "Moderate", examples: "Key cases" },
  { mode: "high", tools_exposed: 25, fields_shown: "All fields", descriptions: "Full", examples: "All cases" },
];

const DEFAULT_SCHEMA = `{
  "name": "GITHUB_LIST_ISSUES",
  "description": "List issues in a repository.",
  "parameters": {
    "type": "object",
    "properties": {
      "owner": {"type": "string"},
      "repo": {"type": "string"},
      "state": {"type": "string", "enum": ["open", "closed", "all"]},
      "labels": {"type": "string"},
      "assignee": {"type": "string"},
      "per_page": {"type": "integer"},
      "archived": {"type": "boolean"}
    },
    "required": ["owner", "repo"]
  }
}`;

export default function SchemaCompaction() {
  const [samples, setSamples] = useState<SchemaSample[]>([]);
  const [schemaInput, setSchemaInput] = useState(DEFAULT_SCHEMA);
  const [customResult, setCustomResult] = useState<SchemaSample | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet("/api/schema/sample").then((res) => setSamples(res.samples ?? []));
  }, []);

  const compactCustom = async () => {
    setLoading(true);
    setError(null);
    try {
      const schema = JSON.parse(schemaInput);
      const res = await apiPost("/api/schema/compact", { schema });
      if (res.error) {
        setError(res.error);
        setCustomResult(null);
      } else {
        setCustomResult(res);
      }
    } catch (e) {
      setError(`Invalid JSON: ${(e as Error).message}`);
      setCustomResult(null);
    } finally {
      setLoading(false);
    }
  };

  const totalSaved = samples.reduce((s, x) => s + x.saved, 0);
  const totalJson = samples.reduce((s, x) => s + x.json_tokens, 0);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Schema Compaction</h1>
        <p className="text-muted-foreground mt-1">
          Type-grouped tool schemas — port of itrummer/schemacompression to JSON Schema.
          Lossless for the LLM, ~30-50% smaller than raw OpenAI tool definitions.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {EFFORT_MODES.map((cfg) => (
          <Card key={cfg.mode}>
            <CardContent className="pt-6">
              <p className="font-semibold capitalize">{cfg.mode} Effort</p>
              <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                <p>Tools exposed: {cfg.tools_exposed}</p>
                <p>Fields: {cfg.fields_shown}</p>
                <p>Descriptions: {cfg.descriptions}</p>
                <p>Examples: {cfg.examples}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {samples.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-medium">Type-Grouped Compaction (live)</CardTitle>
              <div className="flex gap-2">
                <Badge variant="secondary">{totalJson.toLocaleString()} → {(totalJson - totalSaved).toLocaleString()} tokens</Badge>
                <Badge>{totalJson > 0 ? Math.round((totalSaved / totalJson) * 100) : 0}% saved</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {samples.map((s) => (
              <div key={s.name} className="border rounded-md p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <p className="font-mono text-sm">{s.name}</p>
                  <div className="flex gap-2 text-xs">
                    <Badge variant="outline">JSON {s.json_tokens}</Badge>
                    <Badge variant="default">Compact {s.compact_tokens}</Badge>
                    <Badge variant="secondary">{s.savings_percent}% off</Badge>
                  </div>
                </div>
                <pre className="text-xs bg-muted p-3 rounded-md overflow-auto whitespace-pre-wrap">{s.compact}</pre>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Compact Your Own Schema</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={schemaInput}
            onChange={(e) => setSchemaInput(e.target.value)}
            className="w-full h-56 font-mono text-xs p-3 border rounded-md bg-background"
            spellCheck={false}
          />
          <div className="flex items-center gap-3">
            <Button onClick={compactCustom} disabled={loading}>
              {loading ? "Compacting..." : "Compact"}
            </Button>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          {customResult && (
            <div className="border rounded-md p-3 space-y-2 bg-muted/40">
              <div className="flex gap-2 text-xs">
                <Badge variant="outline">JSON {customResult.json_tokens}</Badge>
                <Badge variant="default">Compact {customResult.compact_tokens}</Badge>
                <Badge variant="secondary">{customResult.savings_percent}% off</Badge>
              </div>
              <pre className="text-xs bg-background p-3 rounded-md overflow-auto whitespace-pre-wrap">
                {customResult.compact}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
