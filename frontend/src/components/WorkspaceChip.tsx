interface WorkspaceChipProps {
  workspace?: string;
  initial?: string;
  identity?: string;
}

/**
 * Sidebar identity chip: avatar tile with single-letter initial, workspace
 * name, and a small caret icon hint. Mirrors Composio's `K · Khai K ·
 * uqeueu_workspace` block. Click does nothing for now — it's a hook for a
 * future workspace switcher.
 */
export function WorkspaceChip({
  workspace = "default_project",
  initial = "A",
  identity = "Aperture",
}: WorkspaceChipProps) {
  return (
    <button
      type="button"
      className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md border border-sidebar-border hover:border-primary/40 hover:bg-sidebar-accent/50 transition-colors group"
    >
      <span className="flex-none w-7 h-7 rounded-md bg-primary text-primary-foreground flex items-center justify-center text-[13px] font-semibold tracking-tight">
        {initial}
      </span>
      <div className="flex-1 min-w-0 text-left">
        <p className="text-[12px] font-medium leading-tight truncate">{identity}</p>
        <p className="text-[10px] text-muted-foreground leading-tight truncate font-mono">
          {workspace}
        </p>
      </div>
      <svg
        className="w-3 h-3 text-muted-foreground group-hover:text-foreground transition-colors flex-none"
        viewBox="0 0 12 12"
        fill="none"
      >
        <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
