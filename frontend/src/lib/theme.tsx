import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ThemePref = "light" | "dark" | "device";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "aperture.theme.v1";

interface ThemeContextValue {
  pref: ThemePref;          // user-chosen preference (light / dark / device)
  resolved: ResolvedTheme;  // what's actually applied
  setPref: (next: ThemePref) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readSystem(): ResolvedTheme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

function readStoredPref(): ThemePref {
  if (typeof window === "undefined") return "device";
  const v = window.localStorage.getItem(STORAGE_KEY);
  if (v === "light" || v === "dark" || v === "device") return v;
  return "device";
}

function applyTheme(resolved: ResolvedTheme): void {
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  root.classList.add(resolved);
  root.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(() => readStoredPref());
  const [system, setSystem] = useState<ResolvedTheme>(() => readSystem());

  // Watch system preference for the "device" mode.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const listener = (e: MediaQueryListEvent) => {
      setSystem(e.matches ? "light" : "dark");
    };
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, []);

  const resolved: ResolvedTheme = pref === "device" ? system : pref;

  // Apply on every change to the DOM root.
  useEffect(() => {
    applyTheme(resolved);
  }, [resolved]);

  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage may be disabled — silently skip
    }
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ pref, resolved, setPref }),
    [pref, resolved, setPref],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
