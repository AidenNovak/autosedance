"use client";

import { useI18n } from "@/components/I18nProvider";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function normalizeTheme(v: unknown): Theme {
  // Backward compatibility:
  // - old: "anime" -> light
  // - old: "default" -> dark
  if (v === "light" || v === "anime") return "light";
  if (v === "dark" || v === "default") return "dark";
  return "light";
}

function setThemeCookie(theme: Theme) {
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `autos_theme=${theme}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export function ThemeToggle({ initialTheme }: { initialTheme: Theme }) {
  const { t } = useI18n();
  const [theme, setTheme] = useState<Theme>(() => normalizeTheme(initialTheme));

  // Keep state aligned with SSR-chosen theme.
  useEffect(() => {
    const raw = normalizeTheme(document.documentElement.dataset.theme);
    if (raw !== theme) setTheme(raw);
  }, []);

  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className={theme === "dark" ? "btn" : "btn primary"}
      aria-pressed={theme === "dark"}
      title={theme === "dark" ? t("theme.to_light") : t("theme.to_dark")}
      onClick={() => {
        setTheme(next);
        document.documentElement.dataset.theme = next;
        setThemeCookie(next);
      }}
    >
      {next === "dark" ? t("theme.dark") : t("theme.light")}
    </button>
  );
}
