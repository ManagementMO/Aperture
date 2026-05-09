import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import {
  ArrowDownWideNarrow,
  BarChart3,
  FlaskConical,
  LayoutTemplate,
  Sparkles,
} from "lucide-react";
import { CommandPalette } from "@/components/CommandPalette";
import { WorkspaceChip } from "@/components/WorkspaceChip";
import { Background } from "@/components/Background";

interface NavItem {
  path: string;
  label: string;
  icon: typeof BarChart3;
  blurb: string;
}

const navItems: NavItem[] = [
  { path: "/", label: "Demo", icon: Sparkles, blurb: "Run a task end-to-end" },
  { path: "/overview", label: "Overview", icon: BarChart3, blurb: "What we're saving" },
  { path: "/waterfall", label: "Token waterfall", icon: ArrowDownWideNarrow, blurb: "Per-tool flow" },
  { path: "/schema", label: "Schema compaction", icon: LayoutTemplate, blurb: "Tool schemas, smaller" },
  { path: "/benchmarks", label: "Benchmarks", icon: FlaskConical, blurb: "Compression × quality" },
];

function ApertureMark() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M12 2 L12 22 M2 12 L22 12 M5 5 L19 19 M19 5 L5 19"
        stroke="currentColor"
        strokeOpacity="0.4"
        strokeWidth="1"
      />
      <circle cx="12" cy="12" r="3" fill="currentColor" />
    </svg>
  );
}

function titleFor(pathname: string): string {
  return navItems.find((item) => item.path === pathname)?.label ?? "Demo";
}

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <Background />

      <div className="relative z-10 flex min-h-screen">
        <aside className="w-60 border-r border-border/60 bg-sidebar/60 backdrop-blur-sm flex flex-col">
          <div className="p-4 border-b border-border/60 space-y-3">
            <div className="flex items-center gap-2.5">
              <span className="text-foreground"><ApertureMark /></span>
              <div className="flex flex-col leading-tight">
                <span className="text-[15px] font-semibold tracking-tight">Aperture</span>
                <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Token efficiency layer
                </span>
              </div>
            </div>
            <WorkspaceChip workspace="default_project" initial="A" identity="Aperture" />
          </div>

          <nav className="flex-1 p-3 overflow-auto">
            <p className="px-2 pb-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80 font-medium">
              Surfaces
            </p>
            <div className="space-y-0.5">
              {navItems.map((item) => {
                const active = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`group flex items-start gap-3 px-2.5 py-2 rounded-md transition-colors ${
                      active
                        ? "bg-sidebar-accent text-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                    }`}
                  >
                    <span
                      className={`mt-0.5 flex-none w-1 h-4 rounded-full ${
                        active ? "bg-primary" : "bg-transparent"
                      }`}
                    />
                    <Icon
                      className={`mt-0.5 w-3.5 h-3.5 flex-none ${
                        active ? "text-foreground" : "text-muted-foreground/70 group-hover:text-foreground"
                      }`}
                    />
                    <div className="min-w-0 leading-tight">
                      <p className={`text-[13px] ${active ? "font-medium" : ""}`}>{item.label}</p>
                      <p className="text-[10px] text-muted-foreground/70 truncate">
                        {item.blurb}
                      </p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </nav>

          <div className="px-4 py-3 border-t border-border/60 space-y-1">
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="lime-dot" />
              <span className="num">v0.2.0</span>
              <span className="text-muted-foreground/40">·</span>
              <span>local</span>
            </div>
            <p className="text-[10px] text-muted-foreground/60 leading-tight">
              Every number on screen is measured by Aperture.
            </p>
          </div>
        </aside>

        <main className="flex-1 overflow-auto">
          <header className="sticky top-0 z-20 backdrop-blur bg-background/70 border-b border-border/50">
            <div className="max-w-6xl mx-auto px-8 h-12 flex items-center justify-between">
              <div className="flex items-center gap-3 text-[12px] text-muted-foreground">
                <span className="lime-dot" />
                <span>Aperture</span>
                <span className="text-muted-foreground/40">/</span>
                <span className="text-foreground">{titleFor(location.pathname)}</span>
              </div>
              <CommandPalette />
            </div>
          </header>
          <div className="max-w-6xl mx-auto px-8 py-7">{children}</div>
        </main>
      </div>
    </div>
  );
}
