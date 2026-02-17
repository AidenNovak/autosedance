import type { Metadata } from "next";
import Link from "next/link";
import { cookies, headers } from "next/headers";
import { Fraunces, Space_Grotesk, IBM_Plex_Mono } from "next/font/google";

import { I18nProvider } from "@/components/I18nProvider";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { getMessages, isRtl, resolveLocale, t as translate } from "@/i18n";

import "./globals.css";

const sans = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap"
});

const serif = Fraunces({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap"
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-mono",
  display: "swap"
});

export const metadata: Metadata = {
  title: "AutoSedance",
  description: "Interactive AI video workflow (manual upload) with continuity control."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieLocale = cookies().get("autos_lang")?.value || null;
  const acceptLanguage = headers().get("accept-language");
  const locale = resolveLocale({ cookieLocale, acceptLanguage });
  const messages = getMessages(locale);

  return (
    <html
      lang={locale}
      dir={isRtl(locale) ? "rtl" : "ltr"}
      className={`${sans.variable} ${serif.variable} ${mono.variable}`}
    >
      <body>
        <I18nProvider initialLocale={locale}>
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
                  <Link className="btn" href="/i18n">
                    {translate(messages, "topbar.translations")}
                  </Link>
                  <Link className="btn primary" href="/new">
                    {translate(messages, "topbar.new_project")}
                  </Link>
                  <LanguageSwitcher />
                </div>
              </div>
            </div>
          </div>
          <div className="container" style={{ padding: "18px 0 46px" }}>
            {children}
          </div>
        </I18nProvider>
      </body>
    </html>
  );
}
