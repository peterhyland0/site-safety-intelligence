import { useState } from "react";
import { currentTheme, setTheme, type Theme } from "../lib/theme";
import { IconMoon, IconSun } from "./Icons";

/** Header button that switches between light and dark. Shows the mode it will switch to. */
export function ThemeToggle() {
  const [theme, setState] = useState<Theme>(currentTheme);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => {
        setTheme(next);
        setState(next);
      }}
      className="grid min-h-10 min-w-10 place-items-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-ink"
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {next === "light" ? <IconSun size={18} /> : <IconMoon size={18} />}
    </button>
  );
}
