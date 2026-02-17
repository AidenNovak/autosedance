"use client";

import { useMemo } from "react";

import { useI18n } from "@/components/I18nProvider";
import { getAllMessages, SUPPORTED_LOCALES } from "@/i18n";

export default function I18nPage() {
  const { t } = useI18n();

  const all = useMemo(() => getAllMessages(), []);
  const keys = useMemo(() => Object.keys(all.en || {}).sort(), [all]);

  return (
    <div className="card">
      <div className="hd">
        <h2>{t("i18n.title")}</h2>
        <span className="pill">{SUPPORTED_LOCALES.length}</span>
      </div>
      <div className="bd">
        <div className="muted">{t("i18n.subtitle")}</div>
        <div style={{ height: 12 }} />

        <div style={{ display: "grid", gap: 10 }}>
          {keys.map((key) => (
            <div key={key} className="card" style={{ boxShadow: "none" }}>
              <div className="hd">
                <h2 style={{ fontSize: 13, margin: 0, fontFamily: "var(--font-mono)" }}>{key}</h2>
                <span className="pill">{key.includes("{") ? "params" : "text"}</span>
              </div>
              <div className="bd" style={{ display: "grid", gap: 8 }}>
                {SUPPORTED_LOCALES.map((loc) => (
                  <div
                    key={loc}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "140px 1fr",
                      gap: 12,
                      alignItems: "baseline"
                    }}
                  >
                    <div className="muted">{t(`lang.${loc}`)}</div>
                    <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
                      {all[loc]?.[key] ?? t("i18n.missing")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

