import en from "./locales/en.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import zhCN from "./locales/zh-CN.json";
import ar from "./locales/ar.json";
import ja from "./locales/ja.json";

export const SUPPORTED_LOCALES = ["zh-CN", "en", "es", "fr", "ar", "ja"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export type Messages = Record<string, string>;

const DEFAULT_LOCALE: Locale = "en";

const ALL_MESSAGES: Record<Locale, Messages> = {
  "zh-CN": zhCN as Messages,
  en: en as Messages,
  es: es as Messages,
  fr: fr as Messages,
  ar: ar as Messages,
  ja: ja as Messages
};

export function isRtl(locale: Locale): boolean {
  return locale === "ar";
}

export function normalizeLocale(input?: string | null): Locale {
  const raw = (input || "").trim();
  if (!raw) return DEFAULT_LOCALE;

  // Accept-Language might be "en-US,en;q=0.9"; cookie might be "zh-CN".
  const first = raw.split(",")[0]?.trim() || "";
  const lowered = first.replace(/_/g, "-").toLowerCase();

  if (lowered === "zh-cn" || lowered.startsWith("zh")) return "zh-CN";
  if (lowered === "en" || lowered.startsWith("en-")) return "en";
  if (lowered === "es" || lowered.startsWith("es-")) return "es";
  if (lowered === "fr" || lowered.startsWith("fr-")) return "fr";
  if (lowered === "ar" || lowered.startsWith("ar-")) return "ar";
  if (lowered === "ja" || lowered.startsWith("ja-")) return "ja";

  // Exact match fallback.
  for (const loc of SUPPORTED_LOCALES) {
    if (loc.toLowerCase() === lowered) return loc;
  }
  return DEFAULT_LOCALE;
}

export function resolveLocale(opts: { cookieLocale?: string | null; acceptLanguage?: string | null }): Locale {
  const cookieLocale = normalizeLocale(opts.cookieLocale);
  if (opts.cookieLocale && cookieLocale) return cookieLocale;

  // Parse Accept-Language properly: pick the first supported one.
  const header = (opts.acceptLanguage || "").trim();
  if (header) {
    const tokens = header.split(",").map((p) => p.trim()).filter(Boolean);
    for (const tok of tokens) {
      const tag = tok.split(";")[0]?.trim();
      if (!tag) continue;
      const loc = normalizeLocale(tag);
      if (loc) return loc;
    }
  }
  return DEFAULT_LOCALE;
}

export function getMessages(locale: Locale): Messages {
  return ALL_MESSAGES[locale] || ALL_MESSAGES[DEFAULT_LOCALE];
}

export function getAllMessages(): Record<Locale, Messages> {
  return ALL_MESSAGES;
}

const PARAM_RE = /\{([a-zA-Z0-9_]+)\}/g;

export function t(
  messages: Messages,
  key: string,
  params?: Record<string, string | number | boolean | null | undefined>,
  fallbackMessages: Messages = ALL_MESSAGES[DEFAULT_LOCALE]
): string {
  const template = messages[key] ?? fallbackMessages[key] ?? key;
  if (!params) return template;
  return template.replace(PARAM_RE, (_, name) => {
    const v = params[name];
    if (v === null || v === undefined) return `{${name}}`;
    return String(v);
  });
}

