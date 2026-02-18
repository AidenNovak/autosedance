"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { RegisterCard } from "@/components/RegisterCard";
import type { Job, ProjectDetail, SegmentDetail, SegmentSummary } from "@/lib/api";
import {
  backendUrl,
  createJob,
  getJob,
  getProject,
  getSegment,
  updateFullScript,
  updateSegment,
  uploadVideo
} from "@/lib/api";
import { humanizeError } from "@/lib/errors";
import { useI18n } from "@/components/I18nProvider";

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function pad3(n: number) {
  return n.toString().padStart(3, "0");
}

function pad3Display(index0: number) {
  return pad3(index0 + 1);
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

const TERMINAL_JOB_STATUSES = new Set<Job["status"]>(["succeeded", "failed", "canceled"]);

function statusDotClass(status: string) {
  switch (status) {
    case "completed":
      return "dot ok";
    case "failed":
      return "dot bad";
    case "analyzing":
      return "dot warn";
    case "waiting_video":
      return "dot idle";
    case "script_ready":
      return "dot mid";
    default:
      return "dot idle";
  }
}

export default function ProjectPage() {
  const { t, locale } = useI18n();
  const { me, loading: authLoading } = useAuth();
  const authenticated = !!me?.authenticated;
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [segment, setSegment] = useState<SegmentDetail | null>(null);

  const [selectedIndex, setSelectedIndex] = useState(0);

  const [loading, setLoading] = useState(true);
  const [loadingSegment, setLoadingSegment] = useState(false);

  const [busy, setBusy] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const pollingRef = useRef(0);

  const [error, setError] = useState<string | null>(null);

  const [fullFeedback, setFullFeedback] = useState("");
  const [segFeedback, setSegFeedback] = useState("");

  const [fullDraft, setFullDraft] = useState("");
  const [segScriptDraft, setSegScriptDraft] = useState("");
  const [segPromptDraft, setSegPromptDraft] = useState("");
  const [uploadWarnings, setUploadWarnings] = useState<string[]>([]);

  const jobRunning = !!activeJob && !TERMINAL_JOB_STATUSES.has(activeJob.status);
  const locked = !!busy || jobRunning;

  async function refreshProject(opts?: { include_full_script?: boolean; include_canon?: boolean }) {
    const include_full_script = opts?.include_full_script ?? true;
    const include_canon = opts?.include_canon ?? true;
    const p = await getProject(projectId, { include_full_script, include_canon });

    setProject((prev) => {
      if (!prev) return p;
      return {
        ...p,
        full_script: include_full_script ? p.full_script : prev.full_script,
        canon_summaries: include_canon ? p.canon_summaries : prev.canon_summaries
      };
    });

    if (include_full_script) setFullDraft(p.full_script || "");
    return p;
  }

  async function refreshSegment(index: number) {
    setLoadingSegment(true);
    try {
      const s = await getSegment(projectId, index);
      setSegment(s);
      setSegScriptDraft(s.segment_script || "");
      setSegPromptDraft(s.video_prompt || "");
      setUploadWarnings((s.warnings || []).filter((w): w is string => typeof w === "string" && w.length > 0));
      return s;
    } finally {
      setLoadingSegment(false);
    }
  }

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(humanizeError(t, e, t("common.request_failed")));
    } finally {
      setBusy(null);
    }
  }

  async function waitForJob(jobId: string) {
    const myToken = ++pollingRef.current;
    while (true) {
      if (myToken !== pollingRef.current) return null; // canceled by a newer poll
      const j = await getJob(projectId, jobId);
      setActiveJob(j);
      if (TERMINAL_JOB_STATUSES.has(j.status)) return j;
      await sleep(850);
    }
  }

  async function runJob(
    label: string,
    input: { type: Job["type"]; index?: number; feedback?: string },
    afterSuccess?: (finalJob: Job) => Promise<void>
  ) {
    await run(label, async () => {
      const job = await createJob(projectId, { ...input, locale });
      setActiveJob(job);

      const finalJob = await waitForJob(job.id);
      if (!finalJob) return;

      if (finalJob.status !== "succeeded") {
        throw new Error(finalJob.error || `Job ${finalJob.status}`);
      }

      if (afterSuccess) await afterSuccess(finalJob);
    });
  }

  // Initial load
  useEffect(() => {
    if (!authenticated) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const p = await refreshProject({ include_full_script: true, include_canon: true });
        if (cancelled) return;
        const idx = clamp(p.current_segment_index || 0, 0, Math.max(0, p.num_segments - 1));
        setSelectedIndex(idx);
      } catch (e) {
        if (cancelled) return;
        setError(humanizeError(t, e, t("project.failed_load_project")));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      pollingRef.current++;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, authenticated]);

  // Load selected segment detail on change.
  useEffect(() => {
    if (!project) return;
    let cancelled = false;
    setError(null);
    (async () => {
      try {
        await refreshSegment(selectedIndex);
      } catch (e) {
        if (cancelled) return;
        setError(humanizeError(t, e, t("project.failed_load_segment")));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, selectedIndex]);

  const selectedSummary: SegmentSummary | null = useMemo(() => {
    if (!project) return null;
    return project.segments.find((s) => s.index === selectedIndex) || null;
  }, [project, selectedIndex]);

  const canUpload = useMemo(() => {
    if (selectedSummary?.has_video) return true;
    if (segment?.video_url) return true;
    const script = (segment?.segment_script || "").trim();
    const prompt = (segment?.video_prompt || "").trim();
    return script.length > 0 || prompt.length > 0;
  }, [selectedSummary?.has_video, segment?.video_url, segment?.segment_script, segment?.video_prompt]);

  const completedCount = useMemo(() => {
    if (!project) return 0;
    return project.segments.filter((s) => s.status === "completed").length;
  }, [project]);

  const allVideosPresent = useMemo(() => {
    if (!project) return false;
    return project.segments.length > 0 && project.segments.every((s) => s.has_video);
  }, [project]);

  const videoSrc = useMemo(() => {
    if (!segment?.video_url) return null;
    return `${backendUrl()}${segment.video_url}?v=${encodeURIComponent(segment.updated_at)}`;
  }, [segment?.video_url, segment?.updated_at]);

  const frameSrc = useMemo(() => {
    if (!segment?.frame_url) return null;
    return `${backendUrl()}${segment.frame_url}?v=${encodeURIComponent(segment.updated_at)}`;
  }, [segment?.frame_url, segment?.updated_at]);

  const finalSrc = useMemo(() => {
    if (!project?.final_video_path) return null;
    return `${backendUrl()}/api/projects/${projectId}/final?v=${encodeURIComponent(project.updated_at)}`;
  }, [project?.final_video_path, project?.updated_at, projectId]);

  const timeRange = useMemo(() => {
    if (!project) return null;
    const start = selectedIndex * project.segment_duration;
    const end = Math.min((selectedIndex + 1) * project.segment_duration, project.total_duration_seconds);
    return `${start}s - ${end}s`;
  }, [project, selectedIndex]);

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

  if (loading) {
    return (
      <div className="card">
        <div className="bd">
          <div className="muted">{t("common.loading")}</div>
        </div>
      </div>
    );
  }

  if (error && !project) {
    return (
      <div className="card">
        <div className="bd">
          <div style={{ color: "var(--danger)" }}>{error}</div>
          <div style={{ height: 10 }} />
          <Link className="btn" href="/">
            {t("common.back")}
          </Link>
        </div>
      </div>
    );
  }

  if (!project) return null;

  const canonDisplay = useMemo(() => {
    const raw = (project.canon_summaries || "").trim();
    if (!raw) return "";
    return raw
      .split("\n---\n")
      .map((item) => item.replace(/^\[#IDX=\d+\]\s*/, "").trim())
      .filter(Boolean)
      .join("\n---\n");
  }, [project.canon_summaries]);

  function trStatus(status: string): string {
    const key = `status.${status}`;
    const out = t(key);
    return out === key ? status : out;
  }

  function trNext(action: string): string {
    const key = `next.${action}`;
    const out = t(key);
    return out === key ? action : out;
  }

  function trJobType(type: string): string {
    const key = `job.${type}`;
    const out = t(key);
    return out === key ? type : out;
  }

  function trJobStatus(status: string): string {
    const key = `job_status.${status}`;
    const out = t(key);
    return out === key ? status : out;
  }

  return (
    <div className="split">
      <div className="card sidebar">
        <div className="hd">
          <h2>{t("project.segments.title")}</h2>
          <span className="pill">
            {completedCount}/{project.num_segments}
          </span>
        </div>
        <div className="bd" style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "grid", gap: 10 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="pill">{trNext(project.next_action)}</span>
                <span className="pill">
                  {t("project.current", {
                    current:
                      project.current_segment_index >= project.num_segments
                        ? t("common.done")
                        : String(project.current_segment_index + 1)
                  })}
                </span>
              </div>
              <div className="row">
                <button
                  className="btn"
                  onClick={() =>
                  run("refresh_project", async () => {
                    await refreshProject({ include_full_script: false, include_canon: false });
                  })
                }
                disabled={locked}
              >
                {t("common.refresh")}
              </button>
              <button
                className="btn"
                onClick={() => setSelectedIndex(clamp(project.current_segment_index || 0, 0, project.num_segments - 1))}
                disabled={locked}
              >
                {t("project.go_current")}
              </button>
            </div>
          </div>

          <div className="segscroll">
            <div className="seglist">
              {project.segments.map((s) => {
                const active = s.index === selectedIndex;
                return (
                  <button
                    key={s.index}
                    className={`segitem${active ? " active" : ""}`}
                    onClick={() => setSelectedIndex(s.index)}
                    disabled={locked}
                    title={t("project.segment.tooltip", { n: s.index + 1, status: trStatus(s.status) })}
                  >
                    <span className={statusDotClass(s.status)} />
                    <div style={{ display: "grid", gap: 4, flex: 1, minWidth: 0, textAlign: "left" }}>
                      <div className="segtitle">
                        #{pad3Display(s.index)}{" "}
                        {s.index === project.current_segment_index ? (
                          <span className="pill tiny">{t("project.current_badge")}</span>
                        ) : null}
                      </div>
                      <div className="segmeta">
                        {s.has_video ? "V" : "·"} {s.has_frame ? "F" : "·"} {s.has_description ? "D" : "·"} ·{" "}
                        {trStatus(s.status)}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gap: 14 }}>
        <div className="card">
          <div className="hd">
            <h2>{t("project.project.title")}</h2>
            <span className="pill">{project.id}</span>
          </div>
          <div className="bd">
            <div className="kvs">
              <div className="kv">
                <div className="k">{t("project.project.duration")}</div>
                <div className="v">{project.total_duration_seconds}s</div>
              </div>
              <div className="kv">
                <div className="k">{t("project.project.pacing")}</div>
                <div className="v">{project.pacing}</div>
              </div>
              <div className="kv">
                <div className="k">{t("project.project.segments")}</div>
                <div className="v">
                  {completedCount}/{project.num_segments}
                </div>
              </div>
            </div>
            <div style={{ marginTop: 12 }} className="muted">
              {t("project.project.prompt", { prompt: project.user_prompt })}
            </div>
            {error ? (
              <div style={{ marginTop: 12, color: "var(--danger)" }}>{error}</div>
            ) : null}
          </div>
        </div>

        {activeJob ? (
          <div className="card">
            <div className="hd">
              <h2>{t("project.job.title")}</h2>
              <span className="pill">
                {trJobType(activeJob.type)} · {trJobStatus(activeJob.status)}
              </span>
	            </div>
	            <div className="bd" style={{ display: "grid", gap: 10 }}>
	              <div className="muted" style={{ lineHeight: 1.5 }}>
	                {(() => {
	                  const ui = (activeJob.result as any)?.ui_message as any;
	                  if (ui && typeof ui.key === "string") {
	                    const out = t(ui.key, ui.params);
	                    if (out !== ui.key) return out;
	                  }
	                  return activeJob.message || "…";
	                })()}
	              </div>
	              <div className="progress">
	                <div style={{ width: `${clamp(activeJob.progress || 0, 0, 100)}%` }} />
	              </div>
              {activeJob.error ? <div style={{ color: "var(--danger)" }}>{activeJob.error}</div> : null}
            </div>
          </div>
        ) : null}

        <div className="grid two">
          <div className="card">
            <div className="hd">
              <h2>{t("project.in0.title")}</h2>
              <div className="row">
                <button
                  className="btn primary"
                  onClick={() =>
                    runJob(
                      "job_full_script",
                      { type: "full_script", feedback: fullFeedback.trim() || undefined },
                      async () => {
                        setFullFeedback("");
                        const p = await refreshProject({ include_full_script: true, include_canon: true });
                        const idx = clamp(p.current_segment_index || 0, 0, Math.max(0, p.num_segments - 1));
                        setSelectedIndex(idx);
                        await refreshSegment(idx);
                      }
                    )
                  }
                  disabled={locked}
                >
                  {jobRunning && activeJob?.type === "full_script"
                    ? t("common.generating")
                    : project.full_script
                      ? t("common.regenerate")
                      : t("common.generate")}
                </button>
                <button
                  className="btn"
                  onClick={() =>
                    run("save_full", async () => {
                      const p = await updateFullScript(projectId, fullDraft, true);
                      setProject(p);
                      setFullDraft(p.full_script || "");
                      const idx = clamp(p.current_segment_index || 0, 0, Math.max(0, p.num_segments - 1));
                      setSelectedIndex(idx);
                      await refreshSegment(idx);
                    })
                  }
                  disabled={locked}
                >
                  {busy === "save_full" ? t("common.saving") : t("common.save")}
                </button>
              </div>
            </div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("project.feedback.optional")}</div>
                <input
                  className="input"
                  value={fullFeedback}
                  onChange={(e) => setFullFeedback(e.target.value)}
                  placeholder={t("project.feedback.full_placeholder")}
                  disabled={locked}
                />
              </div>
              <textarea
                className="textarea"
                value={fullDraft}
                onChange={(e) => setFullDraft(e.target.value)}
                placeholder={t("project.full.placeholder")}
                disabled={locked}
              />
            </div>
          </div>

          <div className="card">
            <div className="hd">
              <h2>{t("project.continuity.title")}</h2>
              <span className="pill">{t("project.continuity.last3")}</span>
            </div>
            <div className="bd">
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--muted)", fontSize: 12, lineHeight: 1.55 }}>
                {canonDisplay || t("project.continuity.empty")}
              </pre>
            </div>
          </div>
        </div>

        <div className="grid two">
          <div className="card">
            <div className="hd">
              <h2>
                {t("project.segment.title", { n: pad3Display(selectedIndex) })}{" "}
                {timeRange ? <span className="pill tiny">{timeRange}</span> : null}
              </h2>
              <span className="pill">
                {trStatus((segment?.status || selectedSummary?.status || "pending") as any)}
              </span>
            </div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div className="row">
                  <button
                    className="btn"
                    onClick={() => setSelectedIndex((i) => clamp(i - 1, 0, project.num_segments - 1))}
                    disabled={locked || selectedIndex <= 0}
                  >
                    {t("project.segment.prev")}
                  </button>
                  <button
                    className="btn"
                    onClick={() => setSelectedIndex((i) => clamp(i + 1, 0, project.num_segments - 1))}
                    disabled={locked || selectedIndex >= project.num_segments - 1}
                  >
                    {t("project.segment.next")}
                  </button>
                </div>

                <div className="row">
                  <button
                    className="btn primary"
                    onClick={() =>
                      runJob(
                        "job_seg_gen",
                        { type: "segment_generate", index: selectedIndex, feedback: segFeedback.trim() || undefined },
                        async () => {
                          setSegFeedback("");
                          await refreshProject({ include_full_script: false, include_canon: false });
                          await refreshSegment(selectedIndex);
                        }
                      )
                    }
                    disabled={locked || !project.full_script}
                    title={!project.full_script ? t("project.in0.generate_first_title") : ""}
                  >
                    {jobRunning && activeJob?.type === "segment_generate" ? t("common.generating") : t("project.segment.generate")}
                  </button>
                  <button
                    className="btn"
                    onClick={() =>
                      run("seg_save", async () => {
                        const p = await updateSegment(projectId, selectedIndex, {
                          segment_script: segScriptDraft,
                          video_prompt: segPromptDraft,
                          invalidate_downstream: true
                        });
                        setProject(p);
                        await refreshSegment(selectedIndex);
                      })
                    }
                    disabled={locked}
                  >
                    {busy === "seg_save" ? t("common.saving") : t("project.segment.save")}
                  </button>
                </div>
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("project.feedback.optional")}</div>
                <input
                  className="input"
                  value={segFeedback}
                  onChange={(e) => setSegFeedback(e.target.value)}
                  placeholder={t("project.feedback.segment_placeholder")}
                  disabled={locked}
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("project.segment.script_label")}</div>
                <textarea
                  className="textarea"
                  value={segScriptDraft}
                  onChange={(e) => setSegScriptDraft(e.target.value)}
                  disabled={locked || loadingSegment}
                />
              </div>

              <div style={{ display: "grid", gap: 6 }}>
                <div className="muted">{t("project.segment.prompt_label")}</div>
                <textarea
                  className="textarea"
                  value={segPromptDraft}
                  onChange={(e) => setSegPromptDraft(e.target.value)}
                  disabled={locked || loadingSegment}
                />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="hd">
              <h2>{t("project.upload.title")}</h2>
              <span className="pill">{t("project.upload.mode")}</span>
            </div>
              <div className="bd" style={{ display: "grid", gap: 12 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                <div className="muted">{t("project.upload.for_segment", { n: pad3Display(selectedIndex) })}</div>
                <label
                  className="btn"
                  style={!canUpload || locked ? { opacity: 0.6, cursor: "not-allowed" } : undefined}
                  title={!canUpload ? t("project.upload.generate_first_title") : undefined}
                >
                  {busy === "upload" ? t("project.upload.uploading") : t("project.upload.choose_file")}
                  <input
                    type="file"
                    accept="video/*"
                    style={{ display: "none" }}
                    disabled={locked || !canUpload}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      run("upload", async () => {
                        const seg = await uploadVideo(projectId, selectedIndex, f);
                        setSegment(seg);
                        setSegScriptDraft(seg.segment_script || "");
                        setSegPromptDraft(seg.video_prompt || "");
                        setUploadWarnings((seg.warnings || []).filter((w): w is string => typeof w === "string" && w.length > 0));
                        await refreshProject({ include_full_script: false, include_canon: false });
                      });
                    }}
                  />
                </label>
              </div>

              {!loadingSegment && !canUpload ? (
                <div style={{ color: "var(--accent)", fontSize: 13, lineHeight: 1.5 }}>
                  {t("project.upload.generate_first_hint")}
                </div>
              ) : null}

              {videoSrc ? <video className="video" controls src={videoSrc} /> : <div className="muted">{t("project.upload.no_video")}</div>}

              {uploadWarnings.length > 0 ? (
                <div style={{ color: "var(--danger)", fontSize: 13, lineHeight: 1.5 }}>
                  {uploadWarnings.map((w, i) => (
                    <div key={i}>{w}</div>
                  ))}
                </div>
              ) : null}

              <div className="row" style={{ justifyContent: "space-between" }}>
                <button
                  className="btn"
                  onClick={() =>
                    runJob(
                      "job_extract_frame",
                      { type: "extract_frame", index: selectedIndex },
                      async () => {
                        await refreshProject({ include_full_script: false, include_canon: false });
                        await refreshSegment(selectedIndex);
                      }
                    )
                  }
                  disabled={locked || !segment?.video_url}
                >
                  {jobRunning && activeJob?.type === "extract_frame"
                    ? t("project.frame.extracting")
                    : t("project.frame.retry_extract")}
                </button>

                <button
                  className="btn"
                  onClick={() => {
                    if (!segment?.frame_url) return;
                    const url = `${backendUrl()}/api/projects/${projectId}/segments/${selectedIndex}/frame/download`;
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `frame_${pad3Display(selectedIndex)}.jpg`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                  }}
                  disabled={locked || !segment?.frame_url}
                >
                  {t("project.frame.save")}
                </button>
              </div>

              <button
                className="btn primary"
                onClick={() =>
                  runJob(
                    "job_analyze",
                    { type: "analyze", index: selectedIndex },
                    async () => {
                      const prevCurrent = project.current_segment_index || 0;
                      const p = await refreshProject({ include_full_script: false, include_canon: true });
                      await refreshSegment(selectedIndex);
                      // Match the legacy flow: analyzing the current segment advances to the next.
                      if (selectedIndex === prevCurrent) {
                        const idx = clamp(p.current_segment_index || 0, 0, Math.max(0, p.num_segments - 1));
                        setSelectedIndex(idx);
                      }
                    }
                  )
                }
                disabled={locked || !segment?.video_url}
              >
                {jobRunning && activeJob?.type === "analyze" ? t("project.analyzing") : t("project.analyze")}
              </button>

              {frameSrc ? <img className="img" src={frameSrc} alt={t("project.frame.alt")} /> : null}

              {segment?.video_description ? (
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--text)", fontSize: 12, lineHeight: 1.55 }}>
                  {segment.video_description}
                </pre>
              ) : (
                <div className="muted">{t("project.analysis.none")}</div>
              )}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="hd">
            <h2>{t("project.assemble.title")}</h2>
            <span className="pill">{allVideosPresent ? t("project.assemble.ready") : t("project.assemble.needs_videos")}</span>
          </div>
          <div className="bd" style={{ display: "grid", gap: 12 }}>
            <div className="row">
              <button
                className="btn primary"
                onClick={() =>
                  runJob("job_assemble", { type: "assemble" }, async () => {
                    await refreshProject({ include_full_script: false, include_canon: false });
                  })
                }
                disabled={locked || !allVideosPresent}
              >
                {jobRunning && activeJob?.type === "assemble"
                  ? t("project.assemble.assembling")
                  : t("project.assemble.button")}
              </button>
              <button
                className="btn"
                onClick={() =>
                  run("refresh_project_full", async () => {
                    await refreshProject({ include_full_script: false, include_canon: false });
                    await refreshSegment(selectedIndex);
                  })
                }
                disabled={locked}
              >
                {t("common.refresh")}
              </button>
            </div>
            {finalSrc ? <video className="video" controls src={finalSrc} /> : <div className="muted">{t("project.final.none")}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
