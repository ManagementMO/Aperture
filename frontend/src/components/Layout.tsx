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
      { path: "/waterfall", label: "Token Waterfall", icon: ArrowDownWideNarrow },
      { path: "/compression", label: "Compression", icon: Minimize2 },
      { path: "/schema", label: "Schema Compaction", icon: LayoutTemplate },
      { path: "/cache", label: "Cache Stats", icon: Database },
      { path: "/benchmarks", label: "Benchmarks", icon: FlaskConical },
    ],
  },
  {
    title: "Optimizations",
    items: [
      { path: "/task-aware", label: "Task-Aware", icon: Target },
      { path: "/placeholder", label: "Placeholders", icon: CloudCog },
      { path: "/prompt-cache", label: "Prompt Cache", icon: Layers },
      { path: "/field-select", label: "Field Select", icon: Filter },
    ],
  },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      <aside className="w-64 border-r bg-card flex flex-col">
        <div className="p-6 border-b">
          <h1 className="text-xl font-semibold tracking-tight">Aperture</h1>
          <p className="text-xs text-muted-foreground mt-1">Tool Context Control Plane</p>
        </div>
        <nav className="flex-1 p-3 space-y-4 overflow-auto">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="px-3 pb-1 text-[11px] uppercase tracking-wider text-muted-foreground/80 font-medium">
                {section.title}
              </p>
              <div className="space-y-1">
                {section.items.map((item) => {
                  const active = location.pathname === item.path;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                        active
                          ? "bg-primary text-primary-foreground font-medium"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <div className="p-4 border-t text-xs text-muted-foreground">
          Composio Agent Efficiency Layer
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
