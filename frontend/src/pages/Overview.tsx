import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TerminalBlock, type TerminalLine } from "@/components/TerminalBlock";

interface DatasetInfo {
  items: number;
  raw_tokens: number;
}

interface Health {
  status?: string;
  version?: string;
}

const STRATEGIES: { key: string; label: string; detail: string }[] = [
  { key: "01", label: "Token attribution", detail: "Tiktoken counts per schema, argument, raw + compressed result." },
  { key: "02", label: "Effort routing", detail: "low / medium / high / auto — calibrated to ask difficulty." },
  { key: "03", label: "Schema-aware compression", detail: "Tool normalizers, field pruning, TOON for tabular." },
  { key: "04", label: "Quality gate", detail: "Walk modes from cheapest until required signals survive." },
  { key: "05", label: "Safe caching", detail: "Exact-match scoped cache; writes & auth never cached." },
];

const TERMINAL_LINES: TerminalLine[] = [
  { kind: "command", text: "uv run python scripts/vanilla_vs_aperture.py" },
  { kind: "output", text: "research_repo  raw=22,146  aperture=6,563    saved 70%" },
  { kind: "output", text: "triage_bugs    raw=11,351  aperture=3,195    saved 72%" },
  { kind: "output", text: "datasets       raw=453,896 aperture=117,180  saved 74%" },
  { kind: "comment", text: "9 quality probes — every signal preserved" },
  { kind: "spinner", text: "Composing… cost  $1.2185 → $0.3173" },
];

export default function Overview() {
  const [datasets, setDatasets] = useState<Record<string, DatasetInfo>>({});
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    apiGet("/api/health").then(setHealth);
    apiGet("/api/datasets").then(setDatasets);
  }, []);

  const totalItems = Object.values(datasets).reduce((s, d) => s + d.items, 0);
  const totalTokens = Object.values(datasets).reduce((s, d) => s + d.raw_tokens, 0);
  const online = health?.status === "ok";

  return (
    <div className="space-y-7">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          <span className={`lime-dot ${online ? "" : "opacity-30"}`} />
          {online ? "online" : "offline"} · api v{health?.version ?? "—"}
        </div>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">Overview</h1>
        <p className="text-muted-foreground text-sm mt-2 max-w-3xl">
          Aperture sits between Composio agents and the LLM. It measures token cost on the way in,
          compresses tool results on the way out, and caches what's safe to cache — every number
          on this dashboard comes from <span className="font-mono">tiktoken</span>, no estimates.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Datasets</p>
            <p className="text-2xl font-semibold metric-value">{Object.keys(datasets).length}</p>
            <p className="text-xs text-muted-foreground">live in <span className="font-mono">data/</span></p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Records</p>
            <p className="text-2xl font-semibold metric-value">{totalItems.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">across all sources</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Raw tokens</p>
            <p className="text-2xl font-semibold metric-value">{totalTokens.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">measured by tiktoken</p>
          </CardContent>
        </Card>
        <Card className="border-primary/30">
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-primary">API status</p>
            <Badge
              variant={online ? "default" : "destructive"}
              className={online ? "bg-primary text-primary-foreground" : ""}
            >
              {online ? "Online" : "Offline"}
            </Badge>
            <p className="text-xs text-muted-foreground">
              {online ? `version ${health?.version}` : "start the FastAPI backend"}
            </p>
          </CardContent>
        </Card>
      </div>

      <TerminalBlock lines={TERMINAL_LINES} animate />

      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-[13px] font-medium">Datasets</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground text-[11px] uppercase tracking-[0.12em] text-left">
                  <th className="pb-2 font-medium">Source</th>
                  <th className="pb-2 font-medium text-right">Items</th>
                  <th className="pb-2 font-medium text-right">Raw tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {Object.entries(datasets).map(([name, info]) => (
                  <tr key={name}>
                    <td className="py-2 font-mono text-xs">{name}</td>
                    <td className="py-2 text-right metric-value">{info.items.toLocaleString()}</td>
                    <td className="py-2 text-right metric-value">{info.raw_tokens.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-[13px] font-medium">What Aperture does</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2.5">
              {STRATEGIES.map((s) => (
                <li key={s.key} className="flex gap-3">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground w-6 pt-1 metric-value">
                    {s.key}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-medium leading-snug">{s.label}</p>
                    <p className="text-xs text-muted-foreground leading-snug">{s.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
