"use client";

import { useEffect, useState } from "react";

type Theme = "default" | "anime";

function normalizeTheme(v: unknown): Theme {
  return v === "anime" ? "anime" : "default";
}

function setThemeCookie(theme: Theme) {
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `autos_theme=${theme}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export function ThemeToggle({ initialTheme }: { initialTheme: Theme }) {
  const [theme, setTheme] = useState<Theme>(() => normalizeTheme(initialTheme));

  // Keep state aligned with SSR-chosen theme.
  useEffect(() => {
    const current = normalizeTheme(document.documentElement.dataset.theme);
    if (current !== theme) setTheme(current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const next: Theme = theme === "anime" ? "default" : "anime";

  return (
    <button
      type="button"
      className={theme === "anime" ? "btn" : "btn primary"}
      aria-pressed={theme === "anime"}
      title={theme === "anime" ? "Switch to default theme" : "Switch to anime theme"}
      onClick={() => {
        setTheme(next);
        document.documentElement.dataset.theme = next;
        setThemeCookie(next);
      }}
    >
      {theme === "anime" ? "Default UI" : "Anime UI"}
    </button>
  );
}
