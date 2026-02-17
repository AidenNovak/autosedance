"use client";

import { useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useI18n } from "@/components/I18nProvider";

function trAuthError(t: (k: string, p?: any) => string, raw: string): string {
  switch (raw) {
    case "AUTH_REQUIRED":
      return t("auth.err.auth_required");
    case "AUTH_DISABLED":
      return t("auth.err.auth_disabled");
    case "EMAIL_INVALID":
      return t("auth.err.email_invalid");
    case "EMAIL_NOT_ALLOWED":
      return t("auth.err.email_not_allowed");
    case "OTP_TOO_FREQUENT":
      return t("auth.err.otp_too_frequent");
    case "OTP_SEND_FAILED":
      return t("auth.err.otp_send_failed");
    case "CODE_INVALID":
      return t("auth.err.code_invalid");
    case "CODE_EXPIRED":
      return t("auth.err.code_expired");
    case "INTERNAL_ERROR":
      return t("auth.err.internal_error");
    default:
      return raw;
  }
}

export function AuthWidget() {
  const { t } = useI18n();
  const { me, loading, requestCode, verifyCode, logout } = useAuth();

  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<null | "send" | "verify" | "logout">(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const authenticated = !!me?.authenticated;
  const emailLabel = useMemo(() => {
    return (me?.email || "").trim();
  }, [me?.email]);

  if (loading && !me) {
    return <span className="pill">{t("auth.loading")}</span>;
  }

  if (authenticated) {
    return (
      <div className="row" style={{ gap: 8 }}>
        <span className="pill" title={emailLabel || undefined}>
          {emailLabel || t("auth.signed_in")}
        </span>
        <button
          className="btn danger"
          disabled={busy === "logout"}
          onClick={async () => {
            setBusy("logout");
            setErr(null);
            setMsg(null);
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
      </div>
    );
  }

  return (
    <details
      className="auth-pop"
      open={open}
      onToggle={(e) => {
        const next = (e.target as HTMLDetailsElement).open;
        setOpen(next);
        if (!next) {
          setStage("email");
          setMsg(null);
          setErr(null);
          setCode("");
        }
      }}
    >
      <summary className="btn">{t("auth.sign_in")}</summary>
      <div className="auth-panel">
        <div style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div className="muted" style={{ fontSize: 12 }}>
              {t("auth.email")}
            </div>
            <input
              className="input"
              placeholder={t("auth.email_placeholder")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={busy !== null || stage === "code"}
              inputMode="email"
              autoComplete="email"
            />
          </div>

          {stage === "code" ? (
            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted" style={{ fontSize: 12 }}>
                {t("auth.code")}
              </div>
              <input
                className="input"
                placeholder={t("auth.code_placeholder")}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                disabled={busy !== null}
                inputMode="numeric"
                autoComplete="one-time-code"
              />
            </div>
          ) : null}

          {msg ? (
            <div className="muted" style={{ fontSize: 12, lineHeight: 1.4 }}>
              {msg}
            </div>
          ) : null}
          {err ? (
            <div style={{ color: "var(--danger)", fontSize: 12, lineHeight: 1.4 }}>
              {err}
            </div>
          ) : null}

          <div className="row" style={{ justifyContent: "space-between" }}>
            {stage === "email" ? (
              <button
                className="btn primary"
                disabled={busy !== null || !email.trim()}
                onClick={async () => {
                  setBusy("send");
                  setErr(null);
                  setMsg(null);
                  try {
                    await requestCode(email.trim());
                    setStage("code");
                    setMsg(t("auth.code_sent"));
                  } catch (e) {
                    setErr(e instanceof Error ? trAuthError(t, e.message) : t("common.request_failed"));
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                {busy === "send" ? t("auth.sending") : t("auth.send_code")}
              </button>
            ) : (
              <button
                className="btn primary"
                disabled={busy !== null || !email.trim() || !code.trim()}
                onClick={async () => {
                  setBusy("verify");
                  setErr(null);
                  setMsg(null);
                  try {
                    await verifyCode(email.trim(), code.trim());
                    setOpen(false);
                  } catch (e) {
                    setErr(e instanceof Error ? trAuthError(t, e.message) : t("common.request_failed"));
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                {busy === "verify" ? t("auth.verifying") : t("auth.verify")}
              </button>
            )}
            <button
              className="btn"
              disabled={busy !== null}
              onClick={() => {
                if (stage === "code") {
                  setStage("email");
                  setCode("");
                  setMsg(null);
                  setErr(null);
                } else {
                  setOpen(false);
                }
              }}
            >
              {stage === "code" ? t("auth.back") : t("auth.close")}
            </button>
          </div>
        </div>
      </div>
    </details>
  );
}

