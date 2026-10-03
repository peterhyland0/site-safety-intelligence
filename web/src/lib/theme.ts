/** Light/dark choice. Follows the system until the viewer picks one; the choice is kept per browser. */
export type Theme = "light" | "dark";

const KEY = "ssi-theme";
const PAGE: Record<Theme, string> = { light: "#f6f6f3", dark: "#121211" }; // --page in index.css

export function systemTheme(): Theme {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function savedTheme(): Theme | null {
  try {
    const t = window.localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : null;
  } catch {
    return null;
  }
}

export function currentTheme(): Theme {
  return savedTheme() ?? systemTheme();
}

export function setTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute("content", PAGE[t]));
  try {
    window.localStorage.setItem(KEY, t);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}
