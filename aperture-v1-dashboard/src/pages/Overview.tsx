import { useEffect, useState } from "react";
import { api, HealthResponse, UsageBucket, CacheBucket } from "../api";

export function Overview() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [topTools, setTopTools] = useState<UsageBucket[]>([]);
  const [topSavings, setTopSavings] = useState<CacheBucket[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([
      api.health(),
      api.inputTokensContributed({ group_by: "meta_tool_slug", page_size: 5 }),
      api.cacheTokensSaved({ group_by: "tool_slug", page_size: 5 }),
    ]).then(([h, t, c]) => {
      if (!alive) return;
      if (h.status === "fulfilled") setHealth(h.value);
      if (t.status === "fulfilled") setTopTools(t.value.data);
      if (c.status === "fulfilled") setTopSavings(c.value.data);
      const errs = [h, t, c].filter((r) => r.status === "rejected") as PromiseRejectedResult[];
      if (errs.length > 0) setError(String(errs[0].reason));
    });
    return () => {
      alive = false;
    };
  }, []);

  const totalTokens = topTools.reduce(
    (sum, b) => sum + b.total_input_tokens_contributed,
    0
  );
  const totalSaved = topSavings.reduce((sum, b) => sum + b.tokens_saved, 0);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Overview</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        Live token + cache stats from the Aperture v3.1 API. Data sourced from
        the SQLite event log populated by the proxy.
      </p>

      {error && (
        <div
          style={{
            padding: 12,
            background: "rgba(255,80,80,0.08)",
            border: "1px solid var(--red)",
            borderRadius: 6,
            marginBottom: 16,
            color: "var(--red)",
            fontSize: 13,
          }}
        >
          API error: {error} — make sure the v3.1 backend is running on port 8002.
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <Card label="Aperture version" value={health?.aperture_version ?? "—"} />
        <Card
          label="SQLite log"
          value={health?.sqlite_log_configured ? "configured" : "not configured"}
        />
        <Card label="Token events" value={String(health?.token_event_count ?? 0)} />
        <Card label="Cache events" value={String(health?.cache_event_count ?? 0)} />
      </div>

      <Section title="Top meta tools by input tokens">
        <Bars
          rows={topTools.map((b) => ({
            label: String(b.group_value ?? "(unknown)"),
            value: b.total_input_tokens_contributed,
            secondary: `${b.total_calls} calls · avg ${Math.round(b.average_per_call)}t`,
          }))}
        />
        {topTools.length === 0 && <Empty />}
      </Section>

      <Section title="Top tools by tokens saved (cache hits)">
        <Bars
          rows={topSavings.map((b) => ({
            label: String(b.group_value ?? "(unknown)"),
            value: b.tokens_saved,
            secondary: `${b.hits} hits · ${b.api_calls_avoided} API calls avoided`,
          }))}
          color="var(--green)"
        />
        {topSavings.length === 0 && <Empty />}
      </Section>

      <div style={{ marginTop: 32, color: "var(--muted)", fontSize: 13 }}>
        Aggregate: {totalTokens.toLocaleString()} tokens contributed ·{" "}
        {totalSaved.toLocaleString()} tokens saved
      </div>
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: 16,
        background: "var(--panel)",
        border: "1px solid var(--border)",
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: 12, color: "var(--muted)" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginTop: 24 }}>
      <h3 style={{ fontSize: 14, color: "var(--muted)", marginBottom: 8 }}>{title}</h3>
      <div
        style={{
          background: "var(--panel)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        {children}
      </div>
    </section>
  );
}

interface BarRow {
  label: string;
  value: number;
  secondary?: string;
}

function Bars({ rows, color = "var(--accent)" }: { rows: BarRow[]; color?: string }) {
  if (rows.length === 0) return null;
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {rows.map((r) => (
        <div key={r.label}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
            <span>{r.label}</span>
            <span style={{ color: "var(--muted)" }}>{r.value.toLocaleString()}</span>
          </div>
          <div
            style={{
              background: "rgba(255,255,255,0.04)",
              height: 6,
              borderRadius: 3,
              marginTop: 4,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${(r.value / max) * 100}%`,
                height: "100%",
                background: color,
              }}
            />
          </div>
          {r.secondary && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{r.secondary}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function Empty() {
  return (
    <div style={{ color: "var(--muted)", fontSize: 13 }}>
      No data yet. Once the proxy starts handling traffic, this populates.
    </div>
  );
}
