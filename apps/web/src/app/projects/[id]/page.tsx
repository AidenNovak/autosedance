"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import type { Project, Segment } from "@/lib/api";
import {
  analyzeSegment,
  assemble,
  backendUrl,
  generateFullScript,
  generateSegment,
  getProject,
  updateFullScript,
  updateSegment,
  uploadVideo
} from "@/lib/api";

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [fullFeedback, setFullFeedback] = useState("");
  const [segFeedback, setSegFeedback] = useState("");

  const [fullDraft, setFullDraft] = useState("");
  const [segScriptDraft, setSegScriptDraft] = useState("");
  const [segPromptDraft, setSegPromptDraft] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const p = await getProject(projectId);
      setProject(p);
      setFullDraft(p.full_script || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [projectId]);

  const currentIndex = useMemo(() => {
    if (!project) return 0;
    return clamp(project.current_segment_index || 0, 0, Math.max(0, project.num_segments - 1));
  }, [project]);

  const currentSegment: Segment | null = useMemo(() => {
    if (!project) return null;
    return project.segments.find((s) => s.index === currentIndex) || null;
  }, [project, currentIndex]);

  const videoSrc = useMemo(() => {
    if (!currentSegment?.video_url) return null;
    return `${backendUrl()}${currentSegment.video_url}`;
  }, [currentSegment]);

  const frameSrc = useMemo(() => {
    if (!currentSegment?.frame_url) return null;
    return `${backendUrl()}${currentSegment.frame_url}?t=${Date.now()}`;
  }, [currentSegment]);

  const finalSrc = useMemo(() => {
    if (!project?.final_video_path) return null;
    return `${backendUrl()}/api/projects/${projectId}/final?t=${Date.now()}`;
  }, [project?.final_video_path, projectId]);

  useEffect(() => {
    if (!currentSegment) {
      setSegScriptDraft("");
      setSegPromptDraft("");
      return;
    }
    setSegScriptDraft(currentSegment.segment_script || "");
    setSegPromptDraft(currentSegment.video_prompt || "");
  }, [currentSegment?.index, currentSegment?.segment_script, currentSegment?.video_prompt]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="bd">
          <div className="muted">Loading…</div>
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
            Back
          </Link>
        </div>
      </div>
    );
  }

  if (!project) return null;

  const allCompleted = project.segments.length === project.num_segments && project.segments.every((s) => s.status === "completed");

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div className="card">
        <div className="hd">
          <h2>Project</h2>
          <span className="pill">{project.next_action}</span>
        </div>
        <div className="bd">
          <div className="kvs">
            <div className="kv">
              <div className="k">ID</div>
              <div className="v">{project.id}</div>
            </div>
            <div className="kv">
              <div className="k">Duration</div>
              <div className="v">
                {project.total_duration_seconds}s ({project.num_segments} segments)
              </div>
            </div>
            <div className="kv">
              <div className="k">Pacing</div>
              <div className="v">{project.pacing}</div>
            </div>
          </div>
          <div style={{ marginTop: 12 }} className="muted">
            Prompt: {project.user_prompt}
          </div>
          {error ? (
            <div style={{ marginTop: 12, color: "var(--danger)" }}>
              {error}
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="hd">
            <h2>in0 Full Script</h2>
            <div className="row">
              <button
                className="btn primary"
                onClick={() =>
                  run("full_script", async () => {
                    const p = await generateFullScript(projectId, fullFeedback.trim() || undefined);
                    setProject(p);
                    setFullDraft(p.full_script || "");
                    setFullFeedback("");
                  })
                }
                disabled={!!busy}
              >
                {busy === "full_script" ? "Generating…" : project.full_script ? "Regenerate" : "Generate"}
              </button>
              <button
                className="btn"
                onClick={() =>
                  run("save_full", async () => {
                    const p = await updateFullScript(projectId, fullDraft, true);
                    setProject(p);
                  })
                }
                disabled={!!busy}
              >
                {busy === "save_full" ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
          <div className="bd" style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Feedback (optional)</div>
              <input className="input" value={fullFeedback} onChange={(e) => setFullFeedback(e.target.value)} placeholder="e.g. add a twist, make it slower, change character…" />
            </div>
            <textarea className="textarea" value={fullDraft} onChange={(e) => setFullDraft(e.target.value)} placeholder="Generate in0 first, or paste your own." />
          </div>
        </div>

        <div className="card">
          <div className="hd">
            <h2>Continuity Context</h2>
            <span className="pill">last 3 summaries</span>
          </div>
          <div className="bd">
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--muted)", fontSize: 12, lineHeight: 1.55 }}>
              {project.canon_summaries || "No canon summaries yet."}
            </pre>
          </div>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <div className="hd">
            <h2>
              Segment {currentIndex} / {project.num_segments - 1}
            </h2>
            <span className="pill">{currentSegment?.status || "pending"}</span>
          </div>
          <div className="bd" style={{ display: "grid", gap: 12 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="muted">
                Time: {currentIndex * project.segment_duration}s -{" "}
                {Math.min((currentIndex + 1) * project.segment_duration, project.total_duration_seconds)}s
              </div>
              <div className="row">
                <button
                  className="btn primary"
                  onClick={() =>
                    run("seg_gen", async () => {
                      const p = await generateSegment(projectId, currentIndex, segFeedback.trim() || undefined);
                      setProject(p);
                      setSegFeedback("");
                    })
                  }
                  disabled={!!busy || !project.full_script}
                  title={!project.full_script ? "Generate in0 first" : ""}
                >
                  {busy === "seg_gen" ? "Generating…" : currentSegment ? "Regenerate Segment" : "Generate Segment"}
                </button>
                <button
                  className="btn"
                  onClick={() =>
                    run("seg_save", async () => {
                      const p = await updateSegment(projectId, currentIndex, {
                        segment_script: segScriptDraft,
                        video_prompt: segPromptDraft,
                        invalidate_downstream: true
                      });
                      setProject(p);
                    })
                  }
                  disabled={!!busy}
                >
                  {busy === "seg_save" ? "Saving…" : "Save Segment"}
                </button>
              </div>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Feedback (optional)</div>
              <input
                className="input"
                value={segFeedback}
                onChange={(e) => setSegFeedback(e.target.value)}
                placeholder="e.g. make prompt more cinematic, keep the donkey on the left, match last frame…"
              />
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Segment Script</div>
              <textarea className="textarea" value={segScriptDraft} onChange={(e) => setSegScriptDraft(e.target.value)} />
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Video Prompt</div>
              <textarea className="textarea" value={segPromptDraft} onChange={(e) => setSegPromptDraft(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="hd">
            <h2>Upload + Analyze</h2>
            <span className="pill">manual mp4 upload</span>
          </div>
          <div className="bd" style={{ display: "grid", gap: 12 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="muted">Upload segment_{currentIndex.toString().padStart(3, "0")}.*</div>
              <label className="btn">
                {busy === "upload" ? "Uploading…" : "Choose File"}
                <input
                  type="file"
                  accept="video/*"
                  style={{ display: "none" }}
                  disabled={!!busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    run("upload", async () => {
                      await uploadVideo(projectId, currentIndex, f);
                      await refresh();
                    });
                  }}
                />
              </label>
            </div>

            {videoSrc ? (
              <video className="video" controls src={videoSrc} />
            ) : (
              <div className="muted">No uploaded video yet.</div>
            )}

            <button
              className="btn primary"
              onClick={() =>
                run("analyze", async () => {
                  const p = await analyzeSegment(projectId, currentIndex);
                  setProject(p);
                })
              }
              disabled={!!busy || !currentSegment?.video_url}
            >
              {busy === "analyze" ? "Analyzing…" : "Analyze Last Frame"}
            </button>

            {frameSrc ? <img className="img" src={frameSrc} alt="last frame" /> : null}

            {currentSegment?.video_description ? (
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--text)", fontSize: 12, lineHeight: 1.55 }}>
                {currentSegment.video_description}
              </pre>
            ) : (
              <div className="muted">No analysis yet.</div>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="hd">
          <h2>Assemble</h2>
          <span className="pill">{allCompleted ? "ready" : "needs segments"}</span>
        </div>
        <div className="bd" style={{ display: "grid", gap: 12 }}>
          <div className="row">
            <button
              className="btn primary"
              onClick={() =>
                run("assemble", async () => {
                  const p = await assemble(projectId);
                  setProject(p);
                })
              }
              disabled={!!busy || !allCompleted}
            >
              {busy === "assemble" ? "Assembling…" : "Assemble Final Video"}
            </button>
            <button className="btn" onClick={refresh} disabled={!!busy}>
              Refresh Project
            </button>
          </div>
          {finalSrc ? <video className="video" controls src={finalSrc} /> : <div className="muted">No final video yet.</div>}
        </div>
      </div>
    </div>
  );
}

