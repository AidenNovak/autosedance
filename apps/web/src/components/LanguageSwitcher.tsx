"use client";

import { useMemo } from "react";

import type { Locale } from "@/i18n";
import { SUPPORTED_LOCALES, normalizeLocale } from "@/i18n";

import { useI18n } from "./I18nProvider";

function setLangCookie(locale: Locale) {
  // 1 year
  const maxAge = 60 * 60 * 24 * 365;
  document.cookie = `autos_lang=${encodeURIComponent(locale)}; path=/; max-age=${maxAge}; samesite=lax`;
}

export function LanguageSwitcher(props?: {
  minWidth?: number;
  reload?: boolean;
  ariaLabel?: string;
  beforeReload?: () => void;
}) {
  const { locale, setLocale, t } = useI18n();
  const minWidth = props?.minWidth ?? 160;
  const reload = props?.reload ?? true;
  const ariaLabel = props?.ariaLabel ?? t("reg.lang_label");

  const options = useMemo(() => {
    return SUPPORTED_LOCALES.map((loc) => ({
      value: loc,
      label: t(`lang.${loc}`)
    }));
  }, [t]);

  return (
    <select
      className="select"
      value={locale}
      onChange={(e) => {
        const next = normalizeLocale(e.target.value);
        setLocale(next);
        setLangCookie(next);
        if (reload) {
          // RootLayout is a Server Component; reload to apply <html lang/dir> and server-rendered strings.
          try {
            props?.beforeReload?.();
          } catch {}
          window.location.reload();
        }
      }}
      style={{ width: "auto", minWidth }}
      aria-label={ariaLabel}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
