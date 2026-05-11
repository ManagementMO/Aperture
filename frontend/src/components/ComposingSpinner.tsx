interface ComposingSpinnerProps {
  label?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}

/**
 * "Composing..." indicator with a spinning ✽. Used wherever Quava is
 * in-flight (waiting on a tool, classifying, compressing, etc.).
 */
export function ComposingSpinner({
  label = "Composing",
  className = "",
  size = "sm",
}: ComposingSpinnerProps) {
  const sizing = {
    sm: { wrap: "text-[12px]", glyph: "text-[14px]", label: "text-[12px]" },
    md: { wrap: "text-sm", glyph: "text-base", label: "text-sm" },
    lg: { wrap: "text-base", glyph: "text-xl", label: "text-base" },
  }[size];

  return (
    <span
      className={`inline-flex items-center gap-2 text-muted-foreground ${sizing.wrap} ${className}`}
      role="status"
      aria-live="polite"
    >
      <span
        aria-hidden
        className={`text-primary leading-none aperture-spin ${sizing.glyph}`}
      >
        ✽
      </span>
      {label && (
        <span className={`font-mono lowercase tracking-tight ${sizing.label}`}>
          {label}…
        </span>
      )}
    </span>
  );
}
