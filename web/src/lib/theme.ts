/** Light/dark choice. Light by default; the viewer's choice is kept per browser. */
export type Theme = "light" | "dark";

const KEY = "ssi-theme";
const HEADER: Record<Theme, string> = { light: "#ffffff", dark: "#0e120d" }; // browser chrome colour

export function savedTheme(): Theme | null {
  try {
    const t = window.localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : null;
  } catch {
    return null;
  }
}

export function currentTheme(): Theme {
  return savedTheme() ?? "light";
}

export function setTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute("content", HEADER[t]));
  try {
    window.localStorage.setItem(KEY, t);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}
