import { useEffect } from "react";
import { createPortal } from "react-dom";
import { Badge } from "@/components/ui/badge";
import { Check, Sparkles, X } from "lucide-react";

interface CompareDialogStep {
  tool: string;
  raw_tokens: number;
  sent_tokens: number;
  raw_bytes?: number;
  sent_bytes?: number;
  saved_percent?: number;
  strategy?: string;
  llm_format?: string;
  cache_status?: string;
  cache_age_seconds?: number;
  composio_cost_avoided_usd?: number;
  raw_preview?: string;
  compressed_preview?: string;
  ultra_summary?: string | null;
  omitted_fields?: string[];
}

interface CompareDialogProps {
  open: boolean;
  step: CompareDialogStep | null;
  onClose: () => void;
}

function fmtN(n?: number): string {
  return (n ?? 0).toLocaleString();
}

export function CompareDialog({ open, step, onClose }: CompareDialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !step) return null;
  const saved = step.saved_percent ?? 0;
  const cacheHit = step.cache_status === "hit";

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center backdrop-blur-md p-6"
      style={{ backgroundColor: "rgba(0, 0, 0, 0.72)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-[1100px] max-h-[88vh] flex flex-col rounded-xl border border-border shadow-2xl shadow-black/60 overflow-hidden"
        style={{ backgroundColor: "var(--aperture-surface-container-high, #161616)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border/60">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              compare · raw ↔ compressed
            </p>
            <h2 className="font-mono text-[14px] text-foreground mt-0.5 truncate">
              {step.tool}
            </h2>
          </div>
          <div className="flex items-center gap-2 flex-none">
            <Badge variant="default" className="text-[10px]">
              {saved.toFixed(1)}% saved
            </Badge>
            {cacheHit && (
              <Badge
                variant="default"
                className="text-[10px]"
                style={{ backgroundColor: "var(--aperture-accent, #31A8FC)" }}
              >
                cache hit · ${(step.composio_cost_avoided_usd ?? 0).toFixed(4)}
              </Badge>
            )}
            <button
              type="button"
              onClick={onClose}
              className="ml-1 inline-flex items-center justify-center w-7 h-7 rounded-md border border-border hover:border-primary/40 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* metric row */}
        <div className="grid grid-cols-4 gap-3 px-5 py-3 border-b border-border/60 text-[11px]">
          <Metric label="raw tokens" value={fmtN(step.raw_tokens)} sub={`${fmtN(step.raw_bytes)} bytes`} />
          <Metric
            label="aperture sent"
            primary
            value={fmtN(step.sent_tokens)}
            sub={`${fmtN(step.sent_bytes)} bytes`}
          />
          <Metric
            label="strategy"
            value={step.strategy || "balanced"}
            sub={`encoding: ${step.llm_format || "json"}`}
            mono
          />
          <Metric
            label="cache"
            value={step.cache_status || "miss"}
            sub={
              step.cache_status === "hit"
                ? `age ${step.cache_age_seconds ?? 0}s`
                : "fresh execution"
            }
            mono
          />
        </div>

        {/* dropped fields chip row */}
        {step.omitted_fields && step.omitted_fields.length > 0 && (
          <div className="px-5 py-2.5 border-b border-border/60 bg-rose-500/[0.04]">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-1.5">
              Quava dropped {step.omitted_fields.length} bookkeeping field
              {step.omitted_fields.length === 1 ? "" : "s"}
            </p>
            <div className="flex flex-wrap gap-1">
              {step.omitted_fields.slice(0, 24).map((f) => (
                <span
                  key={f}
                  className="inline-flex items-center px-1.5 py-0.5 rounded border border-rose-500/30 bg-rose-500/5 text-[10px] font-mono text-rose-300"
                >
                  {f}
                </span>
              ))}
              {step.omitted_fields.length > 24 && (
                <span className="text-[10px] text-muted-foreground">
                  +{step.omitted_fields.length - 24} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* ultra-summary banner */}
        {step.ultra_summary && (
          <div className="px-5 py-2.5 border-b border-border/60 flex items-baseline gap-3">
            <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              ultra-summary
            </span>
            <code className="text-[12px] text-primary font-mono truncate">
              ≡ {step.ultra_summary}
            </code>
          </div>
        )}

        {/* the two terminals — side by side */}
        <div className="flex-1 overflow-hidden grid grid-cols-2 gap-0">
          <PaneTerminal
            title="composio · raw"
            sub={`${fmtN(step.raw_tokens)} tok`}
            content={step.raw_preview || ""}
            tone="muted"
          />
          <PaneTerminal
            title="aperture · sent to claude"
            sub={`${fmtN(step.sent_tokens)} tok`}
            content={step.compressed_preview || ""}
            tone="primary"
          />
        </div>

        {/* footer */}
        <div className="px-5 py-3 border-t border-border/60 text-[11px] text-muted-foreground flex items-center justify-between">
          <span>
            <Check className="inline w-3 h-3 text-primary mr-1" />
            both payloads measured by Quava · esc to close
          </span>
          <span className="font-mono">
            {fmtN(step.raw_tokens)} → {fmtN(step.sent_tokens)} tok · {saved.toFixed(1)}% smaller
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Metric({
  label,
  value,
  sub,
  primary,
  mono,
}: {
  label: string;
  value: string;
  sub?: string;
  primary?: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p
        className={`text-[14px] font-semibold metric-value ${
          primary ? "text-primary" : ""
        }`}
        style={mono ? { fontFamily: "var(--font-mono, monospace)" } : undefined}
      >
        {value}
        {primary && <Sparkles className="inline w-3 h-3 ml-1" />}
      </p>
      {sub && (
        <p className="text-[10px] text-muted-foreground/80 metric-value mt-0.5">
          {sub}
        </p>
      )}
    </div>
  );
}

function PaneTerminal({
  title,
  sub,
  content,
  tone,
}: {
  title: string;
  sub: string;
  content: string;
  tone: "muted" | "primary";
}) {
  return (
    <div
      className={`flex flex-col overflow-hidden ${
        tone === "primary"
          ? "border-l border-primary/30 bg-primary/[0.04]"
          : "border-l border-border/60 bg-black/30"
      }`}
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-border/40 flex-none">
        <p className="text-[11px] font-mono text-foreground/85">{title}</p>
        <span className="text-[10px] text-muted-foreground metric-value">{sub}</span>
      </div>
      <pre className="flex-1 overflow-auto p-4 text-[11px] font-mono leading-[1.5] whitespace-pre-wrap text-foreground/85">
        {content || "(empty)"}
      </pre>
    </div>
  );
}
