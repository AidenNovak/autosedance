"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useI18n } from "@/components/I18nProvider";
import { RegisterCard } from "@/components/RegisterCard";
import { createProject } from "@/lib/api";
import { humanizeError } from "@/lib/errors";

const DURATIONS = [30, 45, 60, 75, 90, 120, 180];

export default function NewProjectPage() {
  const { t } = useI18n();
  const { me, loading: authLoading } = useAuth();
  const authenticated = !!me?.authenticated;
  const router = useRouter();

  const [duration, setDuration] = useState<number>(60);
  const [pacing, setPacing] = useState<"normal" | "slow" | "urgent">("normal");
  const [prompt, setPrompt] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const durationHint = useMemo(() => {
    if (duration % 15 === 0) return "ok";
    return t("new.split_hint", { remainder: duration % 15 });
  }, [duration, t]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const proj = await createProject({
        user_prompt: prompt,
        total_duration_seconds: duration,
        pacing
      });
      router.push(`/projects/${proj.id}`);
    } catch (err) {
      setError(humanizeError(t, err, t("new.failed_create")));
    } finally {
      setLoading(false);
    }
  }

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

  return (
    <div className="grid two">
      <div className="card">
        <div className="hd">
          <h2>{t("new.title")}</h2>
          <span className="pill">{t("new.mode")}</span>
        </div>
        <div className="bd">
          <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">{t("new.total_duration")}</div>
              <div className="row">
                <select
                  className="select"
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value, 10))}
                  style={{ maxWidth: 260 }}
                >
                  {DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {d}s
                    </option>
                  ))}
                </select>
                <input
                  className="input"
                  type="number"
                  min={15}
                  step={15}
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value || "0", 10))}
                  style={{ maxWidth: 180 }}
                />
                <span className="pill">{t("new.segment_label")}</span>
              </div>
              <div className="muted" style={{ fontSize: 13 }}>
                {durationHint === "ok" ? (
                  <span style={{ color: "var(--ok)" }}>{t("new.multiple_of_15")}</span>
                ) : (
                  durationHint
                )}
              </div>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">{t("new.pacing")}</div>
              <select className="select" value={pacing} onChange={(e) => setPacing(e.target.value as any)}>
                <option value="normal">{t("pacing.normal")}</option>
                <option value="slow">{t("pacing.slow")}</option>
                <option value="urgent">{t("pacing.urgent")}</option>
              </select>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">{t("new.prompt")}</div>
              <textarea
                className="textarea"
                placeholder={t("new.prompt_placeholder")}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                required
              />
            </div>

            {error ? <div style={{ color: "var(--danger)" }}>{error}</div> : null}

            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn primary" type="submit" disabled={loading}>
                {loading ? t("common.creating") : t("common.create")}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="hd">
          <h2>{t("new.what_you_get.title")}</h2>
        </div>
        <div className="bd">
          <div className="muted" style={{ lineHeight: 1.7 }}>
            <div>{t("new.what_you_get.line1")}</div>
            <div>{t("new.what_you_get.line2")}</div>
            <div>{t("new.what_you_get.line3")}</div>
            <div>{t("new.what_you_get.line4")}</div>
            <div>{t("new.what_you_get.line5")}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
