import { useEffect, useState } from "react";

interface OverlayEntry {
  original: string;
  optimized: string;
  original_tokens: number;
  optimized_tokens: number;
  reduction_tokens: number;
  reduction_pct: number;
  validation: { cases_run: number; passed: boolean };
  aperture_optimized: boolean;
  aperture_optimizer_version: string;
}

interface OverlayDocument {
  version: number;
  aperture_optimizer_version: string;
  generated_at: string;
  quality_level?: "llm_judged" | "structural_only";
  warning?: string;
  tools: Record<string, Record<string, OverlayEntry>>;
  stats: {
    total_results: number;
    accepted: number;
    rejected: number;
    total_tokens_saved: number;
    min_cases_required?: number;
  };
}

export function SchemaOverlay() {
  const [overlay, setOverlay] = useState<OverlayDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v3.1/overlay")
      .then((r) => {
        if (!r.ok) throw new Error(`overlay API -> ${r.status}`);
        return r.json();
      })
      .then(setOverlay)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div>
        <h2 style={{ marginTop: 0 }}>Schema overlay</h2>
        <p style={{ color: "var(--muted)" }}>
          The overlay endpoint is not accessible. Run the schema optimizer pipeline
          first and start the v3.1 API:
        </p>
        <pre
          style={{
            background: "var(--panel)",
            padding: 12,
            borderRadius: 6,
            fontSize: 12,
            color: "var(--muted)",
          }}
        >
          uv run python -c "from pathlib import Path; from aperture.schema_optimizer.reports
            import optimize_schemas, write_overlay; write_overlay(
            Path('aperture/schema_optimizer/_overlay.json'), optimize_schemas())"
        </pre>
        <div style={{ color: "var(--red)", fontSize: 12 }}>{error}</div>
      </div>
    );
  }

  if (!overlay) {
    return (
      <div>
        <h2 style={{ marginTop: 0 }}>Schema overlay</h2>
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      </div>
    );
  }

  const tools = Object.entries(overlay.tools);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Schema overlay</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        Accepted description rewrites from the schema optimizer. The proxy substitutes
        these into outbound SEARCH_TOOLS / GET_TOOL_SCHEMAS responses.
      </p>

      {overlay.warning && (
        <div
          style={{
            padding: 12,
            background: "rgba(255,180,80,0.10)",
            border: "1px solid var(--orange, #ffaa55)",
            borderRadius: 6,
            marginBottom: 16,
            color: "var(--orange, #ffaa55)",
            fontSize: 12,
          }}
        >
          <strong>{overlay.quality_level?.toUpperCase()}</strong>: {overlay.warning}
        </div>
      )}

      <div style={{ display: "flex", gap: 24, marginBottom: 24 }}>
        <Stat label="Tools optimized" value={String(tools.length)} />
        <Stat label="Total results" value={String(overlay.stats.total_results)} />
        <Stat label="Accepted" value={String(overlay.stats.accepted)} />
        <Stat label="Tokens saved" value={overlay.stats.total_tokens_saved.toLocaleString()} />
        <Stat label="Quality" value={overlay.quality_level ?? "llm_judged"} />
        <Stat label="Optimizer version" value={overlay.aperture_optimizer_version} />
      </div>

      {tools.length === 0 ? (
        <div style={{ color: "var(--muted)" }}>No accepted rewrites yet.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {tools.map(([slug, fields]) => (
            <div
              key={slug}
              style={{
                background: "var(--panel)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 16,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{slug}</div>
              {Object.entries(fields).map(([fieldPath, entry]) => (
                <div key={fieldPath} style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>{fieldPath}</div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 12,
                      marginTop: 6,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>
                        Original ({entry.original_tokens}t)
                      </div>
                      <div style={{ fontSize: 13 }}>{entry.original}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: "var(--green)" }}>
                        Optimized ({entry.optimized_tokens}t · −{Math.round(entry.reduction_pct * 100)}%)
                      </div>
                      <div style={{ fontSize: 13 }}>{entry.optimized}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--muted)" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
