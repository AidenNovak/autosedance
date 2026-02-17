import type { Metadata } from "next";
import Link from "next/link";
import { Fraunces, Space_Grotesk, IBM_Plex_Mono } from "next/font/google";

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
  return (
    <html lang="zh-CN" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body>
        <div className="topbar">
          <div className="container">
            <div className="topbar-inner">
              <div className="brand">
                <Link href="/" className="brand-title">
                  AutoSedance
                </Link>
                <div className="brand-sub">script to segments to video, with continuity</div>
              </div>
              <div className="row">
                <Link className="btn" href="/new">
                  New Project
                </Link>
              </div>
            </div>
          </div>
        </div>
        <div className="container" style={{ padding: "18px 0 46px" }}>
          {children}
        </div>
      </body>
    </html>
  );
}

