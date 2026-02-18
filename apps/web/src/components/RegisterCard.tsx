"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useI18n } from "@/components/I18nProvider";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { OverloadNotice } from "@/components/OverloadNotice";

const REFERRAL_OPTIONS = [
  { value: "x", key: "reg.referral.x" },
  { value: "reddit", key: "reg.referral.reddit" },
  { value: "youtube", key: "reg.referral.youtube" },
  { value: "tiktok", key: "reg.referral.tiktok" },
  { value: "discord", key: "reg.referral.discord" },
  { value: "github", key: "reg.referral.github" },
  { value: "product_hunt", key: "reg.referral.product_hunt" },
  { value: "friend", key: "reg.referral.friend" },
  { value: "other", key: "reg.referral.other" }
] as const;

const REGISTER_DRAFT_KEY = "autos_register_draft_v1";
const REGISTER_DRAFT_TTL_MS = 2 * 60 * 60 * 1000;
const ALLOWED_REFERRALS = new Set<string>(REFERRAL_OPTIONS.map((o) => o.value));

type RegisterDraftSnapshot = {
  mode: "register" | "login";
  invite: string;
  email: string;
  username: string;
  country: string;
  referral: (typeof REFERRAL_OPTIONS)[number]["value"];
  opinion: string;
};

type RegisterDraftV1 = RegisterDraftSnapshot & { v: 1; updatedAt: number };

function isRecord(v: unknown): v is Record<string, any> {
  return typeof v === "object" && v !== null;
}

function clearRegisterDraft() {
  try {
    localStorage.removeItem(REGISTER_DRAFT_KEY);
  } catch {}
}

function readRegisterDraft(now = Date.now()): RegisterDraftSnapshot | null {
  try {
    const raw = localStorage.getItem(REGISTER_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!isRecord(parsed) || parsed.v !== 1) return null;
    const updatedAt = typeof parsed.updatedAt === "number" ? parsed.updatedAt : 0;
    if (!updatedAt || now - updatedAt > REGISTER_DRAFT_TTL_MS) {
      clearRegisterDraft();
      return null;
    }

    const mode = parsed.mode === "login" ? "login" : "register";
    const referralRaw = typeof parsed.referral === "string" ? parsed.referral : "";
    const referral = (ALLOWED_REFERRALS.has(referralRaw) ? referralRaw : "x") as RegisterDraftSnapshot["referral"];

    return {
      mode,
      invite: typeof parsed.invite === "string" ? parsed.invite : "",
      email: typeof parsed.email === "string" ? parsed.email : "",
      username: typeof parsed.username === "string" ? parsed.username : "",
      country: typeof parsed.country === "string" ? parsed.country : "",
      referral,
      opinion: typeof parsed.opinion === "string" ? parsed.opinion : ""
    };
  } catch {
    return null;
  }
}

function writeRegisterDraft(snapshot: RegisterDraftSnapshot, now = Date.now()) {
  try {
    const draft: RegisterDraftV1 = { ...snapshot, v: 1, updatedAt: now };
    localStorage.setItem(REGISTER_DRAFT_KEY, JSON.stringify(draft));
  } catch {}
}

function trAuthError(t: (k: string, p?: any) => string, raw: string): string {
  switch (raw) {
    case "AUTH_DISABLED":
      return t("auth.err.auth_disabled");
    case "AUTH_REQUIRED":
      return t("auth.err.auth_required");
    case "EMAIL_INVALID":
      return t("auth.err.email_invalid");
    case "EMAIL_NOT_ALLOWED":
      return t("auth.err.email_not_allowed");
    case "COUNTRY_INVALID":
      return t("reg.err.country_invalid");
    case "REFERRAL_INVALID":
      return t("reg.err.referral_invalid");
    case "OPINION_TOO_LONG":
      return t("reg.err.opinion_too_long");
    case "INVITE_REQUIRED":
      return t("reg.err.invite_required");
    case "INVITE_INVALID":
      return t("reg.err.invite_invalid");
    case "INVITE_USED":
      return t("reg.err.invite_used");
    case "INVITE_DISABLED":
      return t("reg.err.invite_disabled");
    case "USERNAME_INVALID":
      return t("reg.err.username_invalid");
    case "USERNAME_TAKEN":
      return t("reg.err.username_taken");
    case "PASSWORD_TOO_WEAK":
      return t("reg.err.password_weak");
    case "PASSWORD_TOO_LONG":
      return t("reg.err.password_too_long");
    case "LOGIN_FAILED":
      return t("login.err.failed");
    case "RL_LIMITED":
      return t("auth.err.rl_limited");
    case "OVERLOADED":
      return t("overload.body");
    case "INTERNAL_ERROR":
      return t("common.internal_error");
    default:
      return raw;
  }
}

function genUsernameFromEmail(email: string): string {
  const local = (email.split("@")[0] || "").trim().toLowerCase();
  const base = (local || "user").replace(/[^a-z0-9_]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
  const suffix = Math.random().toString(16).slice(2, 6);
  const candidate = `${base || "user"}_${suffix}`.slice(0, 24);
  return candidate;
}

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

export function RegisterCard() {
  const { t } = useI18n();
  const { register, login } = useAuth();

  const [mode, setMode] = useState<"register" | "login">("register");

  const [invite, setInvite] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [country, setCountry] = useState("");
  const [referral, setReferral] = useState<(typeof REFERRAL_OPTIONS)[number]["value"]>("x");
  const [opinion, setOpinion] = useState("");

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [invites, setInvites] = useState<string[]>([]);
  const [copied, setCopied] = useState<string | null>(null);

  const draftRef = useRef<RegisterDraftSnapshot | null>(null);
  draftRef.current = { mode, invite, email, username, country, referral, opinion };

  useEffect(() => {
    const draft = readRegisterDraft();
    if (!draft) return;
    setMode(draft.mode);
    setInvite(draft.invite);
    setEmail(draft.email);
    setUsername(draft.username);
    setCountry(draft.country);
    setReferral(draft.referral);
    setOpinion(draft.opinion);
  }, []);

  // Best-effort draft persistence so language switching (which triggers a reload)
  // doesn't lose the form inputs.
  useEffect(() => {
    const onHide = () => {
      const snap = draftRef.current;
      if (!snap) return;
      const hasAny = [snap.invite, snap.email, snap.username, snap.country, snap.opinion].some((s) => (s || "").trim());
      if (!hasAny) {
        clearRegisterDraft();
        return;
      }
      writeRegisterDraft(snap);
    };
    window.addEventListener("pagehide", onHide);
    window.addEventListener("beforeunload", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      window.removeEventListener("beforeunload", onHide);
    };
  }, []);

  const referralOptions = useMemo(() => {
    return REFERRAL_OPTIONS.map((o) => ({ ...o, label: t(o.key) }));
  }, [t]);

  const showOverload = err === "OVERLOADED" || err === "RL_LIMITED";
  const showInvites = mode === "register" && invites.length > 0;

  return (
    <div className="center-wrap">
      <div className="card solid" style={{ width: "min(620px, 100%)" }}>
        <div className="hd" style={{ alignItems: "center" }}>
          <h2>{mode === "register" ? t("reg.title") : t("login.title")}</h2>
          <div style={{ marginInlineStart: "auto" }}>
            <LanguageSwitcher
              reload
              minWidth={140}
              beforeReload={() => {
                const snap = draftRef.current;
                if (!snap) return;
                writeRegisterDraft(snap);
              }}
            />
          </div>
        </div>

        <div className="bd">
          <div className="row" style={{ justifyContent: "center", marginBottom: 12 }}>
            <button
              type="button"
              className={mode === "register" ? "btn primary" : "btn"}
              onClick={() => {
                setMode("register");
                setErr(null);
              }}
              disabled={busy}
            >
              {t("reg.tab_register")}
            </button>
            <button
              type="button"
              className={mode === "login" ? "btn primary" : "btn"}
              onClick={() => {
                setMode("login");
                setErr(null);
              }}
              disabled={busy}
            >
              {t("reg.tab_login")}
            </button>
          </div>

          <div className="muted" style={{ lineHeight: 1.6, marginBottom: 14 }}>
            {mode === "register" ? t("reg.subtitle") : t("login.subtitle")}
          </div>

          {showInvites ? (
            <div className="notice">
              <div style={{ fontWeight: 650 }}>{t("reg.invites_title")}</div>
              <div className="muted" style={{ marginTop: 6, lineHeight: 1.55 }}>
                {t("reg.invites_subtitle")}
              </div>
              <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                {invites.map((c) => (
                  <div key={c} className="row" style={{ justifyContent: "space-between", gap: 10 }}>
                    <div dir="ltr" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                      {c}
                    </div>
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
            </div>
          ) : null}

          {showOverload ? <OverloadNotice variant={err === "RL_LIMITED" ? "rate_limited" : "overloaded"} /> : null}

          {!showOverload && err ? (
            <div style={{ color: "var(--danger)", fontSize: 13, lineHeight: 1.5, marginBottom: 12 }}>
              {trAuthError(t, err)}
            </div>
          ) : null}

          {mode === "register" ? (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setErr(null);
                setCopied(null);
                try {
                  const out = await register({
                    invite_code: invite.trim(),
                    email: email.trim(),
                    username: username.trim() ? username.trim() : null,
                    password,
                    country: country.trim(),
                    referral,
                    opinion: opinion.trim() ? opinion.trim() : null
                  });
                  setInvites((out.invites || []).filter((x): x is string => typeof x === "string" && x.length > 0));
                  setPassword("");
                  clearRegisterDraft();
                } catch (e2) {
                  setErr(e2 instanceof Error ? e2.message : "INTERNAL_ERROR");
                } finally {
                  setBusy(false);
                }
              }}
              style={{ display: "grid", gap: 12 }}
            >
              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.invite")}</div>
                <input
                  className="input"
                  placeholder={t("reg.invite_ph")}
                  value={invite}
                  onChange={(e) => setInvite(e.target.value)}
                  disabled={busy}
                  dir="ltr"
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.email")}</div>
                <input
                  className="input"
                  placeholder={t("reg.email_ph")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  inputMode="email"
                  autoComplete="email"
                  disabled={busy}
                  dir="ltr"
                  required
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.username")}</div>
                <div className="row" style={{ gap: 10 }}>
                  <input
                    className="input"
                    placeholder={t("reg.username_ph")}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={busy}
                    style={{ flex: 1, minWidth: 240 }}
                    dir="ltr"
                  />
                  <button
                    type="button"
                    className="btn"
                    onClick={() => setUsername(genUsernameFromEmail(email))}
                    disabled={busy}
                  >
                    {t("reg.username_generate")}
                  </button>
                </div>
                <div className="muted" style={{ fontSize: 12, lineHeight: 1.45 }}>
                  {t("reg.username_note")}
                </div>
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.password")}</div>
                <input
                  className="input"
                  placeholder={t("reg.password_ph")}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={busy}
                  type="password"
                  autoComplete="new-password"
                  required
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.country")}</div>
                <input
                  className="input"
                  placeholder={t("reg.country_ph")}
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  disabled={busy}
                  required
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.referral")}</div>
                <select
                  className="select"
                  value={referral}
                  onChange={(e) => setReferral(e.target.value as any)}
                  disabled={busy}
                  required
                >
                  {referralOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("reg.opinion")}</div>
                <textarea
                  className="textarea"
                  placeholder={t("reg.opinion_ph")}
                  value={opinion}
                  onChange={(e) => setOpinion(e.target.value)}
                  disabled={busy}
                />
              </div>

              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn primary" type="submit" disabled={busy}>
                  {busy ? t("reg.submitting") : t("reg.submit")}
                </button>
              </div>
            </form>
          ) : (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setErr(null);
                try {
                  await login({ username: username.trim(), password });
                  clearRegisterDraft();
                } catch (e2) {
                  setErr(e2 instanceof Error ? e2.message : "INTERNAL_ERROR");
                } finally {
                  setBusy(false);
                }
              }}
              style={{ display: "grid", gap: 12 }}
            >
              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("login.username")}</div>
                <input
                  className="input"
                  placeholder={t("login.username_ph")}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={busy}
                  autoComplete="username"
                  dir="ltr"
                  required
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("login.password")}</div>
                <input
                  className="input"
                  placeholder={t("login.password_ph")}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={busy}
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </div>

              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn primary" type="submit" disabled={busy}>
                  {busy ? t("login.logging_in") : t("login.login")}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
