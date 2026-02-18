"use client";

import { useI18n } from "@/components/I18nProvider";

export function OverloadNotice(props?: { variant?: "overloaded" | "rate_limited" }) {
  const { t } = useI18n();
  const variant = props?.variant || "overloaded";

  const bodyKey = variant === "rate_limited" ? "overload.rate_limited" : "overload.body";

  return (
    <div className="notice" role="status" aria-live="polite">
      <div style={{ fontWeight: 650 }}>{t("overload.title")}</div>
      <div className="muted" style={{ marginTop: 6, lineHeight: 1.55 }}>
        {t(bodyKey)}
      </div>
      <div style={{ height: 10 }} />
      <div className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
        <div>{t("overload.contact_title")}</div>
        <div>{t("overload.contact_x", { handle: "@logiclogic1223" })}</div>
        <div>{t("overload.contact_other", { handle: "aiden_novak" })}</div>
      </div>
    </div>
  );
}

