"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { ProjectSummary } from "@/lib/api";
import { backendUrl, listProjects } from "@/lib/api";
import { useI18n } from "@/components/I18nProvider";

export default function HomePage() {
  const { t } = useI18n();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("home.projects.failed_load"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="grid two">
      <div className="card">
        <div className="hd">
          <h2>{t("home.projects.title")}</h2>
          <div className="row">
            <button className="btn" onClick={refresh} disabled={loading}>
              {t("common.refresh")}
            </button>
            <Link className="btn primary" href="/new">
              {t("common.new")}
            </Link>
          </div>
        </div>
        <div className="bd">
          {error ? <div style={{ color: "var(--danger)" }}>{error}</div> : null}
          {loading ? (
            <div className="muted">{t("common.loading")}</div>
          ) : projects.length === 0 ? (
            <div className="muted">{t("home.projects.empty")}</div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {projects.map((p) => (
                <Link
                  key={p.id}
                  href={`/projects/${p.id}`}
                  className="card"
                  style={{ boxShadow: "none" }}
                >
                  <div className="hd">
                    <h2 style={{ fontSize: 14, margin: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {p.user_prompt.slice(0, 56) || t("home.projects.empty_prompt")}
                    </h2>
                    <span className="pill">
                      {(() => {
                        const key = `next.${p.next_action}`;
                        const label = t(key);
                        return label === key ? p.next_action : label;
                      })()}
                    </span>
                  </div>
                  <div className="bd">
                    <div className="kvs">
                      <div className="kv">
                        <div className="k">{t("home.projects.duration")}</div>
                        <div className="v">{p.total_duration_seconds}s</div>
                      </div>
                      <div className="kv">
                        <div className="k">{t("home.projects.segments")}</div>
                        <div className="v">
                          {p.segments_completed}/{p.num_segments}
                        </div>
                      </div>
                      <div className="kv">
                        <div className="k">{t("home.projects.pacing")}</div>
                        <div className="v">{p.pacing}</div>
                      </div>
                    </div>
                    <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
                      {t("home.projects.stats", {
                        videos: p.segments_with_video,
                        frames: p.segments_with_frame,
                        desc: p.segments_with_description,
                        current:
                          p.current_segment_index >= p.num_segments ? t("common.done") : String(p.current_segment_index + 1)
                      })}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="hd">
          <h2>{t("home.backend.title")}</h2>
          <span className="pill">{backendUrl()}</span>
        </div>
        <div className="bd">
          <div className="muted" style={{ lineHeight: 1.6 }}>
            {t("home.backend.flow")}
          </div>
          <div style={{ height: 12 }} />
          <div className="muted" style={{ lineHeight: 1.6 }}>
            {t("home.backend.tips")}
            <div>{t("home.backend.tip1")}</div>
            <div>{t("home.backend.tip2")}</div>
            <div>{t("home.backend.tip3")}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
