import { useEffect, useState } from "react";
import { apiGet, describeApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GitBranch, Mail, MessageSquare, FileText, ListTodo, Database } from "lucide-react";
import { TerminalBlock, type TerminalLine } from "@/components/TerminalBlock";

interface DatasetInfo {
  items: number;
  raw_tokens: number;
}

interface CacheStat {
  tool_slug: string;
  cache_status: "hit" | "miss" | "bypass" | "not_cacheable";
  cacheable: boolean;
}

const SOURCE_DETAIL: Record<string, {
  source: string;
  shape: string;
  icon: typeof GitBranch;
}> = {
  github_users: { source: "GitHub Users CSV", shape: "10,001 rows × 12 columns", icon: GitBranch },
  notion_pages: { source: "Notion Pages", shape: "500 pages with parent + properties", icon: FileText },
  linear_issues: { source: "Linear Issues", shape: "200 issues with state + assignees", icon: ListTodo },
  supabase_users: { source: "Supabase Users", shape: "1,000 user records", icon: Database },
};

const TERMINAL_LINES: TerminalLine[] = [
  { kind: "command", text: "aperture run \"summarize the dataset chatter\"" },
  { kind: "output", text: "research_repo  raw=22,146  sent=6,563    saved 70%" },
  { kind: "output", text: "triage_bugs    raw=11,351  sent=3,195    saved 72%" },
  { kind: "output", text: "datasets       raw=453,896 sent=117,180  saved 74%" },
  { kind: "comment", text: "9 quality probes — every signal preserved" },
  { kind: "spinner", text: "Composing… cost  $1.2185 → $0.3173" },
];

export default function Overview() {
  const [datasets, setDatasets] = useState<Record<string, DatasetInfo>>({});
  const [cacheStats, setCacheStats] = useState<CacheStat[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([
      apiGet<Record<string, DatasetInfo>>("/api/datasets"),
      apiGet<{ stats: CacheStat[] }>("/api/cache/stats"),
    ]).then(([d, c]) => {
      if (!mounted) return;
      if (d.status === "fulfilled") setDatasets(d.value);
      else setError(describeApiError(d.reason));
      if (c.status === "fulfilled") setCacheStats(c.value.stats ?? []);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const totalItems = Object.values(datasets).reduce((s, d) => s + d.items, 0);
  const totalTokens = Object.values(datasets).reduce((s, d) => s + d.raw_tokens, 0);

  const cacheCount = cacheStats.length;
  const hits = cacheStats.filter((s) => s.cache_status === "hit").length;

  return (
    <div className="space-y-7">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Overview</p>
        <h1 className="text-3xl font-semibold tracking-tight mt-1">What we&apos;re saving</h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
          Every count below is measured by Aperture &mdash; from the bytes the
          tool actually returned to the bytes the LLM actually reads. No estimates.
        </p>
      </div>

      {error && (
        <Card className="border-rose-500/40">
          <CardContent className="pt-4 pb-4">
            <p className="text-[12px] text-rose-300">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Sources</p>
            <p className="text-2xl font-semibold metric-value">{Object.keys(datasets).length}</p>
            <p className="text-xs text-muted-foreground">tool fixtures live</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Records</p>
            <p className="text-2xl font-semibold metric-value">{totalItems.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">across all sources</p>
          </CardContent>
        </Card>
        <Card className="border-primary/30">
          <CardContent className="pt-5 space-y-1">
            <p className="text-[11px] uppercase tracking-[0.14em] text-primary">Raw tokens</p>
            <p className="text-2xl font-semibold metric-value">{totalTokens.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">measured by Aperture</p>
          </CardContent>
        </Card>
      </div>

      <TerminalBlock lines={TERMINAL_LINES} animate />

      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-[13px] font-medium">Where the raw tokens come from</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {Object.entries(datasets).map(([name, info]) => {
              const meta = SOURCE_DETAIL[name];
              const Icon = meta?.icon ?? GitBranch;
              return (
                <div key={name} className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex w-7 h-7 rounded-md border border-border items-center justify-center text-muted-foreground">
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-sm font-medium">{meta?.source ?? name}</p>
                      <p className="text-[12px] metric-value text-muted-foreground">
                        {info.raw_tokens.toLocaleString()}
                      </p>
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {meta?.shape ?? `${info.items.toLocaleString()} items`}
                    </p>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-[13px] font-medium">What a quality gate is</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-[12px] text-muted-foreground leading-relaxed">
            <p>
              Compression alone isn&apos;t enough. A <span className="text-foreground font-medium">quality gate</span> is
              Aperture&apos;s acceptance check &mdash; for every compressed schema we
              verify the values an agent would have used (titles, IDs,
              addressees, statuses) survived the squeeze.
            </p>
            <p>
              If a probe fails, the schema gets rerun at a lighter mode until it
              passes. The agent never sees a payload that lost its signal.
            </p>
            <div className="flex items-center gap-3 pt-1">
              <span className="flex items-center gap-1.5 text-[11px]">
                <GitBranch className="w-3 h-3" /> Repo
              </span>
              <span className="flex items-center gap-1.5 text-[11px]">
                <Mail className="w-3 h-3" /> Inbox
              </span>
              <span className="flex items-center gap-1.5 text-[11px]">
                <MessageSquare className="w-3 h-3" /> Channels
              </span>
              <span className="flex items-center gap-1.5 text-[11px]">
                <ListTodo className="w-3 h-3" /> Issues
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-[13px] font-medium">Cache</CardTitle>
            <Badge variant="secondary" className="text-[10px]">
              {cacheCount} entries · {hits} hits
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1.5">
            {cacheStats.length === 0 && (
              <p className="text-[12px] text-muted-foreground">
                No cache entries yet &mdash; run the demo and these will populate.
              </p>
            )}
            {cacheStats.map((stat, i) => (
              <CacheRow key={i} stat={stat} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CacheRow({ stat }: { stat: CacheStat }) {
  const { tone, blurb } = describeStatus(stat.cache_status, stat.tool_slug);
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 border-b border-border/40 last:border-b-0">
      <div className="flex items-center gap-2 min-w-0">
        <span
          className={`w-1.5 h-1.5 rounded-full flex-none ${
            stat.cache_status === "hit"
              ? "bg-primary"
              : stat.cache_status === "miss"
                ? "bg-foreground/40"
                : "bg-muted-foreground/30"
          }`}
        />
        <span className="font-mono text-[11px] truncate">{stat.tool_slug}</span>
      </div>
      <div className="flex items-center gap-2 flex-none">
        <Badge variant={tone} className="text-[10px] capitalize">
          {stat.cache_status.replace("_", " ")}
        </Badge>
        <span className="text-[11px] text-muted-foreground hidden md:inline">{blurb}</span>
      </div>
    </div>
  );
}

function describeStatus(
  status: CacheStat["cache_status"],
  tool: string,
): { tone: "default" | "secondary" | "outline" | "destructive"; blurb: string } {
  if (status === "hit") return { tone: "default", blurb: "warm read · 0 ms" };
  if (status === "miss") return { tone: "secondary", blurb: "first time we&apos;ve seen this" };
  if (status === "not_cacheable") {
    if (tool.includes("SEND") || tool.includes("WRITE") || tool.includes("CREATE"))
      return { tone: "outline", blurb: "writes are never cached" };
    return { tone: "outline", blurb: "policy: deny by default" };
  }
  return { tone: "outline", blurb: "bypassed by request" };
}
