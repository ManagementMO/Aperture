import { Link, useLocation } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowDownWideNarrow,
  BarChart3,
  Banknote,
  FlaskConical,
  LayoutTemplate,
  PanelLeftClose,
  PanelLeftOpen,
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
  { path: "/",           label: "Run",         icon: Sparkles },
  { path: "/spend",      label: "Spend",       icon: Banknote },
  { path: "/overview",   label: "Overview",    icon: BarChart3 },
  { path: "/waterfall",  label: "Waterfall",   icon: ArrowDownWideNarrow },
  { path: "/schema",     label: "Schema",      icon: LayoutTemplate },
  { path: "/benchmarks", label: "Benchmarks",  icon: FlaskConical },
];

const SIDEBAR_KEY = "quava.sidebar.collapsed";

function QuavaMark({ size = 22 }: { size?: number }) {
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
        {/* Claude-style sidebar — soft, calm, generous breathing room. */}
        <aside
          className={`flex flex-col border-r border-border/40 bg-sidebar/30 backdrop-blur-sm transition-[width] duration-200 ease-out ${
            collapsed ? "w-[58px]" : "w-[232px]"
          }`}
        >
          <div
            className={`flex items-center h-14 ${
              collapsed ? "justify-center" : "px-3 justify-between"
            }`}
          >
            <Link to="/" className="flex items-center gap-2.5 min-w-0">
              <QuavaMark size={22} />
              {!collapsed && (
                <span className="text-[15px] font-semibold tracking-tight">
                  Quava
                </span>
              )}
            </Link>
            {!collapsed && (
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                className="inline-flex items-center justify-center w-7 h-7 rounded-md text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground transition-colors"
                title="Hide sidebar (⌘\\)"
                aria-label="Collapse sidebar"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Always-visible expand button when collapsed — sits right under
              the logo where you naturally look. No more "where's the button". */}
          {collapsed && (
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="mx-auto mt-1 mb-2 inline-flex items-center justify-center w-7 h-7 rounded-md text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground transition-colors"
              title="Show sidebar (⌘\\)"
              aria-label="Expand sidebar"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          )}

          <nav className={`flex-1 overflow-y-auto overflow-x-hidden ${collapsed ? "px-1.5" : "px-2"}`}>
            <ul className="space-y-0.5">
              {navItems.map((item) => {
                const active = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <li key={item.path}>
                    <Link
                      to={item.path}
                      title={collapsed ? item.label : undefined}
                      className={`group flex items-center rounded-lg transition-colors duration-100 ${
                        collapsed ? "h-9 justify-center" : "h-9 gap-2.5 px-2.5"
                      } ${
                        active
                          ? "bg-foreground/[0.07] text-foreground"
                          : "text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground"
                      }`}
                    >
                      <Icon className="w-4 h-4 flex-none" />
                      {!collapsed && (
                        <span className="text-[13.5px] font-medium truncate">{item.label}</span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {!collapsed && (
            <div className="px-4 py-3 border-t border-border/30">
              <p className="text-[10.5px] text-muted-foreground/60 leading-tight">
                Every number on screen is measured by Quava.
              </p>
              <p className="text-[10px] text-muted-foreground/40 mt-1 num">
                v0.2 · local
              </p>
            </div>
          )}
        </aside>

        <main className="flex-1 overflow-auto flex flex-col min-w-0">
          <header className="sticky top-0 z-20 backdrop-blur-md bg-background/80 border-b border-border/30">
            <div className="max-w-[1080px] mx-auto px-6 h-14 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-[13px] text-muted-foreground min-w-0">
                <span className="truncate">Quava</span>
                <span className="text-muted-foreground/30">/</span>
                <span className="text-foreground truncate">
                  {navItems.find((n) => n.path === location.pathname)?.label ?? "Run"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <ThemeSwitcher />
                <CommandPalette />
              </div>
            </div>
          </header>
          <div className="flex-1 max-w-[1080px] mx-auto w-full px-6 py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
