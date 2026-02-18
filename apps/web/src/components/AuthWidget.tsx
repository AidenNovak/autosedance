"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useI18n } from "@/components/I18nProvider";

function trAuthError(t: (k: string, p?: any) => string, raw: string): string {
  switch (raw) {
    case "RL_LIMITED":
      return t("auth.err.rl_limited");
    case "OVERLOADED":
      return t("overload.body");
    case "INTERNAL_ERROR":
      return t("auth.err.internal_error");
    default:
      return raw;
  }
}

export function AuthWidget() {
  const { t } = useI18n();
  const { me, loading, logout } = useAuth();

  const [busy, setBusy] = useState<null | "logout">(null);
  const [err, setErr] = useState<string | null>(null);

  const authenticated = !!me?.authenticated;
  const label = useMemo(() => {
    return (me?.username || me?.email || "").trim();
  }, [me?.username, me?.email]);

  if (loading && !me) {
    return <span className="pill">{t("auth.loading")}</span>;
  }

  if (!authenticated) {
    return (
      <Link className="btn" href="/">
        {t("reg.open")}
      </Link>
    );
  }

  return (
    <div className="row" style={{ gap: 8 }}>
      <span className="pill" title={label || undefined}>
        {label || t("auth.signed_in")}
      </span>
      <button
        className="btn danger"
        disabled={busy === "logout"}
        onClick={async () => {
          setBusy("logout");
          setErr(null);
          try {
            await logout();
          } catch (e) {
            setErr(e instanceof Error ? trAuthError(t, e.message) : t("common.request_failed"));
          } finally {
            setBusy(null);
          }
        }}
      >
        {t("auth.logout")}
      </button>
      {err ? <span style={{ color: "var(--danger)", fontSize: 12 }}>{err}</span> : null}
    </div>
  );
}
