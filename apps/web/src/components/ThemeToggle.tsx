"use client";

import { useI18n } from "@/components/I18nProvider";
import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
type ExplicitTheme = Exclude<Theme, "system">;

function normalizeTheme(v: unknown): Theme {
  // Backward compatibility:
  // - old: "anime" -> light
  // - old: "default" -> dark
  if (v === "light" || v === "anime") return "light";
  if (v === "dark" || v === "default") return "dark";
  if (v === "system") return "system";
  return "system";
}

function prefersDark(): boolean {
  return !!window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolveEffectiveTheme(theme: Theme): ExplicitTheme {
  if (theme === "system") return prefersDark() ? "dark" : "light";
  return theme;
}

function setThemeCookie(theme: ExplicitTheme) {
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  document.cookie = `autos_theme=${theme}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export function ThemeToggle({ initialTheme }: { initialTheme: Theme }) {
  const { t } = useI18n();
  const [theme, setTheme] = useState<ExplicitTheme>(() => {
    const normalized = normalizeTheme(initialTheme);
    // SSR cannot know system preference; default the button label to "dark" because
    // the base CSS renders dark until the init script runs.
    return normalized === "system" ? "dark" : normalized;
  });

  // Keep state aligned with SSR-chosen theme.
  useEffect(() => {
    const raw = normalizeTheme(document.documentElement.dataset.theme);
    const effective = resolveEffectiveTheme(raw);

    // Ensure we don't stay in a "system" limbo if the init script is blocked.
    if (raw === "system") document.documentElement.dataset.theme = effective;

    if (effective !== theme) setTheme(effective);
  }, []);

  const next: ExplicitTheme = theme === "dark" ? "light" : "dark";

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
      {theme === "dark" ? t("theme.dark") : t("theme.light")}
    </button>
  );
}
