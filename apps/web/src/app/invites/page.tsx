"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { RegisterCard } from "@/components/RegisterCard";
import { useI18n } from "@/components/I18nProvider";
import { OverloadNotice } from "@/components/OverloadNotice";
import { authInvites } from "@/lib/api";
import { humanizeError } from "@/lib/errors";

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

export default function InvitesPage() {
  const { t } = useI18n();
  const { me, loading: authLoading } = useAuth();
  const authenticated = !!me?.authenticated;

  const [invites, setInvites] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const out = await authInvites();
      setInvites((out.invites || []).filter((x): x is string => typeof x === "string" && x.length > 0));
    } catch (e) {
      if (e instanceof Error) {
        if (e.message === "OVERLOADED" || e.message === "RL_LIMITED") {
          setError(e.message);
        } else {
          setError(humanizeError(t, e, t("invites.failed_load")));
        }
      } else {
        setError(t("invites.failed_load"));
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!authenticated) return;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated]);

  if (authLoading && !me) {
    return (
      <div className="card">
        <div className="bd">
          <div className="muted">{t("common.loading")}</div>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return <RegisterCard />;
  }

  const showOverload = error === "OVERLOADED" || error === "RL_LIMITED";

  return (
    <div className="card">
      <div className="hd">
        <h2>{t("invites.title")}</h2>
        <div className="row">
          <button className="btn" onClick={refresh} disabled={loading}>
            {t("common.refresh")}
          </button>
        </div>
      </div>
      <div className="bd">
        <div className="muted" style={{ lineHeight: 1.6, marginBottom: 12 }}>
          {t("invites.subtitle")}
        </div>

        {showOverload ? <OverloadNotice variant={error === "RL_LIMITED" ? "rate_limited" : "overloaded"} /> : null}

        {error && !showOverload ? <div style={{ color: "var(--danger)" }}>{error}</div> : null}

        {loading ? (
          <div className="muted">{t("common.loading")}</div>
        ) : invites.length === 0 ? (
          <div className="muted">{t("invites.empty")}</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {invites.map((c) => (
              <div key={c} className="row" style={{ justifyContent: "space-between", gap: 10 }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{c}</div>
                <button
                  type="button"
                  className="btn"
                  onClick={async () => {
                    const ok = await copyText(c);
                    setCopied(ok ? c : null);
                    setTimeout(() => setCopied(null), 1500);
                  }}
                >
                  {copied === c ? t("reg.copied") : t("reg.copy")}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
