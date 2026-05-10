import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  ArrowDownWideNarrow,
  BarChart3,
  FlaskConical,
  LayoutTemplate,
  Search,
  Sparkles,
} from "lucide-react";

interface PaletteItem {
  id: string;
  label: string;
  hint: string;
  path: string;
  icon: typeof Search;
  keywords: string[];
}

const ITEMS: PaletteItem[] = [
  { id: "demo",       label: "Run",              hint: "/",            icon: Sparkles,             path: "/",            keywords: ["run", "ask", "agent", "input"] },
  { id: "overview",   label: "Overview",          hint: "/overview",    icon: BarChart3,            path: "/overview",    keywords: ["home", "summary", "datasets"] },
  { id: "waterfall",  label: "Token waterfall",   hint: "/waterfall",   icon: ArrowDownWideNarrow,  path: "/waterfall",   keywords: ["schema", "argument", "result"] },
  { id: "schema",     label: "Schema compaction", hint: "/schema",      icon: LayoutTemplate,       path: "/schema",      keywords: ["type-grouped", "tool", "schema"] },
  { id: "benchmarks", label: "Benchmarks",        hint: "/benchmarks",  icon: FlaskConical,         path: "/benchmarks",  keywords: ["modes", "quality"] },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const openPalette = () => {
    setQ("");
    setActive(0);
    setOpen(true);
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => {
          if (!v) {
            setQ("");
            setActive(0);
          }
          return !v;
        });
        return;
      }
      if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  useEffect(() => {
    if (open) {
      // Focus input after the modal mounts.
      const t = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return ITEMS;
    return ITEMS.filter((item) => {
      const hay = (item.label + " " + item.hint + " " + item.keywords.join(" ")).toLowerCase();
      return hay.includes(needle);
    });
  }, [q]);

  const flat = filtered;

  const navigateTo = (item: PaletteItem) => {
    setOpen(false);
    navigate(item.path);
  };

  return (
    <>
      <button
        type="button"
        onClick={openPalette}
        className="accent-hover hidden md:inline-flex items-center gap-2.5 h-8 pl-2.5 pr-1.5 rounded-md border border-border bg-card text-[12px] text-muted-foreground"
      >
        <Search className="w-3.5 h-3.5" />
        <span>Search</span>
        <kbd className="ml-1 px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] text-foreground/70 font-mono">
          ⌘K
        </kbd>
      </button>

      {open && createPortal(
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[14vh] backdrop-blur-md"
          style={{ backgroundColor: "rgba(0, 0, 0, 0.72)" }}
          onClick={() => setOpen(false)}
        >
          <div
            className="w-[560px] max-w-[92vw] rounded-xl border border-border shadow-2xl shadow-black/60 overflow-hidden"
            style={{ backgroundColor: "var(--aperture-surface-container-high, #161616)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2.5 px-3 h-11 border-b border-border">
              <Search className="w-4 h-4 text-muted-foreground" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => { setQ(e.target.value); setActive(0); }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, flat.length - 1)); }
                  if (e.key === "ArrowUp")   { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
                  if (e.key === "Enter" && flat[active]) { e.preventDefault(); navigateTo(flat[active]); }
                }}
                placeholder="Jump to a page or tool…"
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] text-foreground/70 font-mono">esc</kbd>
            </div>
            <div className="max-h-[55vh] overflow-auto py-2">
              {flat.length === 0 && (
                <p className="px-4 py-6 text-center text-sm text-muted-foreground">
                  No matches.
                </p>
              )}
              <div className="px-1.5 pb-1">
                {flat.map((item, flatIdx) => {
                  const isActive = flatIdx === active;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onMouseEnter={() => setActive(flatIdx)}
                      onClick={() => navigateTo(item)}
                      className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-md text-sm transition-colors ${
                        isActive ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${isActive ? "text-primary" : "text-muted-foreground/70"}`} />
                      <span className="flex-1 text-left">{item.label}</span>
                      <span className="text-[11px] font-mono text-muted-foreground/60">{item.hint}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center justify-between px-3 py-2 border-t border-border text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-border bg-muted font-mono">↑↓</kbd>
                navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-border bg-muted font-mono">↵</kbd>
                select
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-border bg-muted font-mono">esc</kbd>
                close
              </span>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
