import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowDownWideNarrow,
  BarChart3,
  CloudCog,
  Database,
  Filter,
  FlaskConical,
  Gauge,
  Layers,
  LayoutTemplate,
  Minimize2,
  Search,
  Target,
} from "lucide-react";

interface PaletteItem {
  id: string;
  label: string;
  hint: string;
  path: string;
  icon: typeof Search;
  group: "Navigation" | "Tools";
  keywords: string[];
}

const ITEMS: PaletteItem[] = [
  { id: "overview",   label: "Overview",          hint: "/", icon: BarChart3,        group: "Navigation", path: "/",            keywords: ["home", "summary", "datasets"] },
  { id: "waterfall",  label: "Token waterfall",   hint: "/waterfall", icon: ArrowDownWideNarrow, group: "Navigation", path: "/waterfall",   keywords: ["schema", "argument", "result"] },
  { id: "compress",   label: "Compression",       hint: "/compression", icon: Minimize2,        group: "Navigation", path: "/compression", keywords: ["mode", "raw", "toon"] },
  { id: "schema",     label: "Schema compaction", hint: "/schema",      icon: LayoutTemplate,   group: "Navigation", path: "/schema",      keywords: ["type-grouped", "tool", "openai"] },
  { id: "cache",      label: "Cache stats",       hint: "/cache",       icon: Database,         group: "Navigation", path: "/cache",       keywords: ["redis", "hit", "miss"] },
  { id: "benchmarks", label: "Benchmarks",        hint: "/benchmarks",  icon: FlaskConical,     group: "Navigation", path: "/benchmarks",  keywords: ["matrix", "modes"] },
  { id: "calibrate",  label: "Effort calibrator", hint: "/calibrate",   icon: Gauge,            group: "Tools",      path: "/calibrate",   keywords: ["auto", "quality", "ask"] },
  { id: "task-aware", label: "Task-aware",        hint: "/task-aware",  icon: Target,           group: "Tools",      path: "/task-aware",  keywords: ["profile", "protected"] },
  { id: "placeholder",label: "Placeholders",      hint: "/placeholder", icon: CloudCog,         group: "Tools",      path: "/placeholder", keywords: ["hydrate", "lazy", "ref"] },
  { id: "prompt",     label: "Prompt cache",      hint: "/prompt-cache",icon: Layers,           group: "Tools",      path: "/prompt-cache",keywords: ["anthropic", "breakpoint", "ttl"] },
  { id: "field",      label: "Field select",      hint: "/field-select",icon: Filter,           group: "Tools",      path: "/field-select",keywords: ["upstream", "fetch"] },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
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
      setQ("");
      setActive(0);
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

  const groups = useMemo(() => {
    const map = new Map<string, PaletteItem[]>();
    for (const item of filtered) {
      if (!map.has(item.group)) map.set(item.group, []);
      map.get(item.group)!.push(item);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const flat = filtered;

  const navigateTo = (item: PaletteItem) => {
    setOpen(false);
    navigate(item.path);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden md:inline-flex items-center gap-2.5 h-8 pl-2.5 pr-1.5 rounded-md border border-border bg-card hover:border-primary/40 hover:bg-sidebar-accent/40 text-[12px] text-muted-foreground transition-colors"
      >
        <Search className="w-3.5 h-3.5" />
        <span>Search</span>
        <kbd className="ml-1 px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] text-foreground/70 font-mono">
          ⌘K
        </kbd>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-[14vh] bg-black/50 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-[560px] max-w-[92vw] rounded-xl border border-border bg-popover shadow-2xl shadow-black/40 overflow-hidden"
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
              {groups.map(([group, items]) => (
                <div key={group} className="px-1.5 pb-1">
                  <p className="px-2.5 pt-2 pb-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80">
                    {group}
                  </p>
                  {items.map((item) => {
                    const flatIdx = flat.indexOf(item);
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
              ))}
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
        </div>
      )}
    </>
  );
}
