import { createContext, useContext, useEffect, useMemo, useState } from "react";

/**
 * Applies the persisted colour theme ("light" | "dark" | "system") and the
 * reading preferences (type scale, line spacing, content font) to the document
 * root. Both are stored in localStorage so they survive reloads.
 */

const PreferencesContext = createContext(null);

const THEME_KEY = "studysync_theme";
const READING_KEY = "studysync_reading";

export const DEFAULT_READING = { scale: "md", leading: "comfortable", font: "sans" };

const SCALE = { sm: "0.9", md: "1", lg: "1.15" };
const LEADING = { compact: "1.4", comfortable: "1.62", relaxed: "1.9" };
const FONT = { sans: "var(--font-main)", serif: "var(--font-title)" };

function readStoredReading() {
  try {
    const parsed = JSON.parse(localStorage.getItem(READING_KEY) || "{}");
    return { ...DEFAULT_READING, ...(parsed && typeof parsed === "object" ? parsed : {}) };
  } catch {
    return DEFAULT_READING;
  }
}

function prefersDark() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function PreferencesProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || "light");
  const [reading, setReading] = useState(readStoredReading);
  const [systemDark, setSystemDark] = useState(prefersDark);

  // Track OS colour-scheme changes while in "system" mode.
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event) => setSystemDark(event.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const resolvedTheme = useMemo(() => {
    if (theme === "system") return systemDark ? "dark" : "light";
    return theme === "dark" ? "dark" : "light";
  }, [theme, systemDark]);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = resolvedTheme;
    root.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement.style;
    root.setProperty("--reading-scale", SCALE[reading.scale] || SCALE.md);
    root.setProperty("--reading-leading", LEADING[reading.leading] || LEADING.comfortable);
    root.setProperty("--reading-font", FONT[reading.font] || FONT.sans);
    localStorage.setItem(READING_KEY, JSON.stringify(reading));
  }, [reading]);

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      resolvedTheme,
      reading,
      setReading,
      updateReading: (patch) => setReading((prev) => ({ ...prev, ...patch })),
      resetReading: () => setReading(DEFAULT_READING),
    }),
    [theme, resolvedTheme, reading]
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error("usePreferences must be used within a PreferencesProvider");
  return ctx;
}
