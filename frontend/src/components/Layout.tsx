import { Link, useLocation } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowDownWideNarrow,
  BarChart3,
  Banknote,
  ChevronsLeft,
  ChevronsRight,
  FlaskConical,
  LayoutTemplate,
  Sparkles,
} from "lucide-react";
import { CommandPalette } from "@/components/CommandPalette";
import { Background } from "@/components/Background";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";

interface NavItem {
  path: string;
  label: string;
  icon: typeof BarChart3;
}

const navItems: NavItem[] = [
  { path: "/",           label: "Run",               icon: Sparkles },
  { path: "/spend",      label: "Spend",             icon: Banknote },
  { path: "/overview",   label: "Overview",          icon: BarChart3 },
  { path: "/waterfall",  label: "Waterfall",         icon: ArrowDownWideNarrow },
  { path: "/schema",     label: "Schema",            icon: LayoutTemplate },
  { path: "/benchmarks", label: "Benchmarks",        icon: FlaskConical },
];

const SIDEBAR_KEY = "quava.sidebar.collapsed";

function QuavaMark({ size = 20 }: { size?: number }) {
  // Single icon glyph from quava-logo.svg (just the diamond mark).
  // The full logo includes the wordmark, so we render a clipped <svg>
  // with just the mark — color comes from currentColor in dark mode and
  // stays brand-blue in light. Using the asset directly avoids a re-export.
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 80 144"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="block flex-none"
    >
      <path
        d="M52.357 104.865 48.5 107.093c-5.26 3.036-11.74 3.036-17 0L13.86 96.908c-5.26-3.037-8.5-8.65-8.5-14.723V75.773L52.357 104.865ZM66.141 47.092c5.26 3.038 8.5 8.65 8.5 14.723v20.37c0 6.073-3.24 11.686-8.5 14.723l-4.578 2.642.752-54.667 3.826 2.21ZM31.5 36.908c5.26-3.037 11.74-3.037 17 0l5.748 3.318L5.36 65.43V61.815c0-6.073 3.24-11.685 8.5-14.722L31.5 36.907Z"
        fill="#31A8FC"
      />
      <path
        d="M31.5 36.908c5.26-3.037 11.74-3.037 17 0l17.641 10.184c5.26 3.038 8.5 8.65 8.5 14.723v20.37c0 6.073-3.24 11.686-8.5 14.723L48.5 107.093c-5.26 3.036-11.74 3.036-17 0L13.86 96.908c-5.26-3.037-8.5-8.65-8.5-14.723V61.815c0-6.073 3.24-11.685 8.5-14.722L31.5 36.907Z"
        stroke="#31A8FC"
        strokeWidth="2"
      />
    </svg>
  );
}

function titleFor(pathname: string): string {
  return navItems.find((item) => item.path === pathname)?.label ?? "Run";
}

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_KEY) === "1";
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
    } catch {
      // storage may be disabled
    }
  }, [collapsed]);

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <Background />

      <div className="relative z-10 flex min-h-screen">
        {/* Sidebar — Cursor-style: subtle, mostly icons when collapsed. */}
        <aside
          className={`flex flex-col border-r border-border/40 bg-sidebar/40 backdrop-blur-sm transition-[width] duration-150 ${
            collapsed ? "w-12" : "w-52"
          }`}
        >
          <div
            className={`flex items-center border-b border-border/40 ${
              collapsed ? "h-12 justify-center" : "h-12 px-3 justify-between"
            }`}
          >
            <Link to="/" className="flex items-center gap-2 min-w-0">
              <QuavaMark size={18} />
              {!collapsed && (
                <span className="text-[13px] font-semibold tracking-tight truncate">
                  Quava
                </span>
              )}
            </Link>
            {!collapsed && (
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                className="text-muted-foreground/60 hover:text-foreground transition-colors"
                title="Collapse sidebar"
                aria-label="Collapse sidebar"
              >
                <ChevronsLeft className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <nav className="flex-1 py-2 overflow-y-auto overflow-x-hidden">
            <ul className="space-y-px px-1.5">
              {navItems.map((item) => {
                const active = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <li key={item.path}>
                    <Link
                      to={item.path}
                      title={collapsed ? item.label : undefined}
                      className={`group flex items-center rounded-md transition-colors ${
                        collapsed
                          ? "h-8 justify-center"
                          : "h-8 gap-2 px-2"
                      } ${
                        active
                          ? "bg-foreground/[0.06] text-foreground"
                          : "text-muted-foreground/80 hover:bg-foreground/[0.04] hover:text-foreground"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5 flex-none" />
                      {!collapsed && (
                        <span className="text-[12.5px] truncate">{item.label}</span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Footer — collapse toggle when expanded; expand handle when collapsed. */}
          <div className="border-t border-border/40 flex items-center justify-center">
            {collapsed ? (
              <button
                type="button"
                onClick={() => setCollapsed(false)}
                className="w-full h-9 flex items-center justify-center text-muted-foreground/60 hover:text-foreground transition-colors"
                title="Expand sidebar"
                aria-label="Expand sidebar"
              >
                <ChevronsRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <div className="w-full px-3 py-2 flex items-center gap-1.5 text-[10px] text-muted-foreground/60">
                <span className="num">v0.2</span>
                <span className="text-muted-foreground/30">·</span>
                <span className="truncate">measured by Quava</span>
              </div>
            )}
          </div>
        </aside>

        <main className="flex-1 overflow-auto">
          <header className="sticky top-0 z-20 backdrop-blur bg-background/70 border-b border-border/30">
            <div className="max-w-7xl mx-auto pl-5 pr-4 h-11 flex items-center justify-between">
              <div className="flex items-center gap-2 text-[12px] text-muted-foreground/80">
                <span>Quava</span>
                <span className="text-muted-foreground/30">/</span>
                <span className="text-foreground">{titleFor(location.pathname)}</span>
              </div>
              <div className="flex items-center gap-2">
                <ThemeSwitcher />
                <CommandPalette />
              </div>
            </div>
          </header>
          <div className="max-w-7xl mx-auto px-5 py-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
