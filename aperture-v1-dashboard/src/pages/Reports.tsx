import { useEffect, useState } from "react";
import { api, UsageBucket } from "../api";

const GROUP_OPTIONS = [
  "meta_tool_slug",
  "toolkit_slug",
  "tool_slug",
  "user_id",
  "session_turn",
  "model",
  "date",
];

export function Reports() {
  const [groupBy, setGroupBy] = useState("meta_tool_slug");
  const [rows, setRows] = useState<UsageBucket[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    api
      .inputTokensContributed({ group_by: groupBy, page_size: 50 })
      .then((res) => {
        if (cancelled) return;
        setRows(res.data);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(String(err));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [groupBy]);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Token reports</h2>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        Aggregate input_tokens_contributed by any dimension. Backed by{" "}
        <code>/api/v3.1/project/usage/input_tokens_contributed</code>.
      </p>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <label style={{ fontSize: 13, color: "var(--muted)" }}>group by</label>
        <select
          value={groupBy}
          onChange={(e) => {
            setGroupBy(e.target.value);
            setLoading(true);
            setError(null);
          }}
          style={{
            background: "var(--panel)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            padding: "6px 12px",
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          {GROUP_OPTIONS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
        {loading && <span style={{ fontSize: 12, color: "var(--muted)" }}>loading…</span>}
      </div>

      {error && (
        <div
          style={{
            padding: 12,
            background: "rgba(255,80,80,0.08)",
            border: "1px solid var(--red)",
            borderRadius: 6,
            color: "var(--red)",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ color: "var(--muted)", textAlign: "left" }}>
            <th style={th}>{groupBy}</th>
            <th style={{ ...th, textAlign: "right" }}>tokens</th>
            <th style={{ ...th, textAlign: "right" }}>calls</th>
            <th style={{ ...th, textAlign: "right" }}>avg/call</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.group_value}-${i}`} style={{ borderTop: "1px solid var(--border)" }}>
              <td style={td}>{String(r.group_value ?? "(unknown)")}</td>
              <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {r.total_input_tokens_contributed.toLocaleString()}
              </td>
              <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {r.total_calls.toLocaleString()}
              </td>
              <td
                style={{
                  ...td,
                  textAlign: "right",
                  fontVariantNumeric: "tabular-nums",
                  color: "var(--muted)",
                }}
              >
                {Math.round(r.average_per_call).toLocaleString()}
              </td>
            </tr>
          ))}
          {rows.length === 0 && !loading && (
            <tr>
              <td colSpan={4} style={{ ...td, color: "var(--muted)", textAlign: "center" }}>
                No data for this group_by.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const th: React.CSSProperties = { padding: "8px 12px", fontWeight: 500 };
const td: React.CSSProperties = { padding: "8px 12px" };
