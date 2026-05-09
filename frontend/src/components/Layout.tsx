import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  ArrowDownWideNarrow,
  Minimize2,
  LayoutTemplate,
  Database,
  FlaskConical,
  Target,
  CloudCog,
  Layers,
  Filter,
  Gauge,
} from "lucide-react";

interface NavItem {
  path: string;
  label: string;
  icon: typeof BarChart3;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const sections: NavSection[] = [
  {
    title: "Measurement",
    items: [
      { path: "/", label: "Overview", icon: BarChart3 },
      { path: "/waterfall", label: "Token waterfall", icon: ArrowDownWideNarrow },
      { path: "/compression", label: "Compression", icon: Minimize2 },
      { path: "/schema", label: "Schema compaction", icon: LayoutTemplate },
      { path: "/cache", label: "Cache stats", icon: Database },
      { path: "/benchmarks", label: "Benchmarks", icon: FlaskConical },
    ],
  },
  {
    title: "Optimizations",
    items: [
      { path: "/calibrate", label: "Effort calibrator", icon: Gauge },
      { path: "/task-aware", label: "Task-aware", icon: Target },
      { path: "/placeholder", label: "Placeholders", icon: CloudCog },
      { path: "/prompt-cache", label: "Prompt cache", icon: Layers },
      { path: "/field-select", label: "Field select", icon: Filter },
    ],
  },
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
        strokeOpacity="0.45"
        strokeWidth="1"
      />
      <circle cx="12" cy="12" r="3" fill="currentColor" />
    </svg>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      <aside className="w-60 border-r border-border bg-sidebar flex flex-col">
        <div className="p-5 border-b border-sidebar-border flex items-center gap-2.5">
          <span className="text-foreground"><ApertureMark /></span>
          <div className="flex flex-col leading-tight">
            <span className="text-[15px] font-semibold tracking-tight">Aperture</span>
            <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Composio · efficiency layer
            </span>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-5 overflow-auto">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="px-2 pb-1.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground/80 font-medium">
                {section.title}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const active = location.pathname === item.path;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`group flex items-center gap-3 px-2.5 py-1.5 rounded-md text-[13px] transition-colors ${
                        active
                          ? "bg-sidebar-accent text-foreground font-medium"
                          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                      }`}
                    >
                      <span
                        className={`relative flex-none w-1 h-4 rounded-full transition-all ${
                          active ? "bg-primary" : "bg-transparent"
                        }`}
                      />
                      <Icon className={`w-3.5 h-3.5 ${active ? "text-foreground" : "text-muted-foreground/70 group-hover:text-foreground"}`} />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="px-4 py-3 border-t border-sidebar-border space-y-1">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="lime-dot" />
            <span className="num">v0.2.0</span>
            <span className="text-muted-foreground/40">·</span>
            <span>local</span>
          </div>
          <p className="text-[10px] text-muted-foreground/60 leading-tight">
            Token cost observability + control plane for Composio.
          </p>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-8 py-7">{children}</div>
      </main>
    </div>
  );
}
