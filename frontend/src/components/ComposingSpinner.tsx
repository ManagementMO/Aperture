interface ComposingSpinnerProps {
  label?: string;
  className?: string;
}

/**
 * The "Composing..." asterisk used across Composio's surfaces during
 * pending tool calls. We use it whenever Aperture is mid-calibration or
 * mid-compression on the dashboard.
 */
export function ComposingSpinner({
  label = "Composing",
  className = "",
}: ComposingSpinnerProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 text-[12px] text-muted-foreground ${className}`}
      role="status"
      aria-live="polite"
    >
      <span className="text-primary text-[14px] leading-none aperture-pulse">✽</span>
      <span className="font-mono lowercase tracking-tight">{label}…</span>
    </span>
  );
}
