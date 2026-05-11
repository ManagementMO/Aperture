import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme, type ThemePref } from "@/lib/theme";

interface Mode {
  value: ThemePref;
  icon: typeof Sun;
  label: string;
}

const MODES: Mode[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "device", icon: Monitor, label: "System" },
  { value: "dark", icon: Moon, label: "Dark" },
];

export function ThemeSwitcher() {
  const { pref, setPref } = useTheme();
  return (
    <div
      className="inline-flex items-center gap-0 h-8 p-0.5 rounded-full"
      style={{ backgroundColor: "color-mix(in oklab, var(--foreground) 8%, transparent)" }}
      role="radiogroup"
      aria-label="Theme"
    >
      {MODES.map(({ value, icon: Icon, label }) => {
        const active = pref === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            onClick={() => setPref(value)}
            title={label}
            className={`inline-flex items-center justify-center w-7 h-7 rounded-[4px] transition-colors ${
              active
                ? "bg-foreground/10 text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-foreground/5"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
          </button>
        );
      })}
    </div>
  );
}
