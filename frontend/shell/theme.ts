import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

/** The same key and values as public/theme-boot.js, which sets the theme before first paint. */
export const THEME_KEY = "renti-theme";
const CHANGE_EVENT = "renti-theme-change";

function readDocumentTheme(): Theme {
  return document.documentElement.dataset["theme"] === "dark" ? "dark" : "light";
}

/** Storage may be blocked (private mode, site data off): a failure never breaks rendering or the toggle. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset["theme"] = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // The choice still applies for this page view; it just will not persist.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY || event.key === null) {
      document.documentElement.dataset["theme"] = event.newValue === "dark" ? "dark" : "light";
      onChange();
    }
  };
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

export function useTheme(): readonly [Theme, () => void] {
  const theme = useSyncExternalStore(subscribe, readDocumentTheme, () => "light" as const);
  const toggle = useCallback(() => {
    applyTheme(readDocumentTheme() === "dark" ? "light" : "dark");
  }, []);
  return [theme, toggle] as const;
}
