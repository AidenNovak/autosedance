import type { Metadata } from "next";
import Link from "next/link";
import { cookies, headers } from "next/headers";

import { I18nProvider } from "@/components/I18nProvider";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { AuthProvider } from "@/components/AuthProvider";
import { AuthWidget } from "@/components/AuthWidget";
import { ThemeToggle } from "@/components/ThemeToggle";
import { getMessages, isRtl, resolveLocale, t as translate } from "@/i18n";

import "./globals.css";
import "./anime.css";

export const metadata: Metadata = {
  title: "AutoSedance",
  description: "Interactive AI video workflow (manual upload) with continuity control."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const ck = cookies();
  const cookieLocale = ck.get("autos_lang")?.value || null;
  const cookieTheme = ck.get("autos_theme")?.value || null;
  const acceptLanguage = headers().get("accept-language");
  const locale = resolveLocale({ cookieLocale, acceptLanguage });
  const messages = getMessages(locale);
  const theme: "light" | "dark" = (() => {
    // Backward compatibility:
    // - old: "anime" -> light
    // - old: "default" -> dark
    if (cookieTheme === "light" || cookieTheme === "anime") return "light";
    if (cookieTheme === "dark" || cookieTheme === "default") return "dark";
    // Default: light (anime).
    return "light";
  })();

  return (
    <html lang={locale} dir={isRtl(locale) ? "rtl" : "ltr"} data-theme={theme}>
      <body>
        <I18nProvider initialLocale={locale}>
          <AuthProvider>
            <div className="topbar">
              <div className="container">
                <div className="topbar-inner">
                  <div className="brand">
                    <Link href="/" className="brand-title">
                      AutoSedance
                    </Link>
                    <div className="brand-sub">{translate(messages, "app.tagline")}</div>
                  </div>
                  <div className="row">
                    <Link className="btn" href="/invites">
                      {translate(messages, "topbar.invites")}
                    </Link>
                    <Link className="btn" href="/i18n">
                      {translate(messages, "topbar.translations")}
                    </Link>
                    <Link className="btn primary" href="/new">
                      {translate(messages, "topbar.new_project")}
                    </Link>
                    <ThemeToggle initialTheme={theme} />
                    <AuthWidget />
                    <LanguageSwitcher />
                  </div>
                </div>
              </div>
            </div>
            <div className="container" style={{ padding: "18px 0 46px" }}>
              {children}
            </div>
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
