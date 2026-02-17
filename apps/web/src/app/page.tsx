"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { ProjectSummary } from "@/lib/api";
import { backendUrl, listProjects } from "@/lib/api";

export default function HomePage() {
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
      setError(e instanceof Error ? e.message : "Failed to load projects");
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
          <h2>Projects</h2>
          <div className="row">
            <button className="btn" onClick={refresh} disabled={loading}>
              Refresh
            </button>
            <Link className="btn primary" href="/new">
              New
            </Link>
          </div>
        </div>
        <div className="bd">
          {error ? <div style={{ color: "var(--danger)" }}>{error}</div> : null}
          {loading ? (
            <div className="muted">Loading…</div>
          ) : projects.length === 0 ? (
            <div className="muted">No projects yet.</div>
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
                      {p.user_prompt.slice(0, 56) || "(empty prompt)"}
                    </h2>
                    <span className="pill">{p.next_action}</span>
                  </div>
                  <div className="bd">
                    <div className="kvs">
                      <div className="kv">
                        <div className="k">Duration</div>
                        <div className="v">{p.total_duration_seconds}s</div>
                      </div>
                      <div className="kv">
                        <div className="k">Segments</div>
                        <div className="v">
                          {p.segments_completed}/{p.num_segments}
                        </div>
                      </div>
                      <div className="kv">
                        <div className="k">Pacing</div>
                        <div className="v">{p.pacing}</div>
                      </div>
                    </div>
                    <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
                      videos: {p.segments_with_video} · frames: {p.segments_with_frame} · desc:{" "}
                      {p.segments_with_description} · current segment: {p.current_segment_index}
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
          <h2>Backend</h2>
          <span className="pill">{backendUrl()}</span>
        </div>
        <div className="bd">
          <div className="muted" style={{ lineHeight: 1.6 }}>
            Flow: generate full script (in0) → generate a 15s segment (inN) → upload video → analyze last frame (inNB +
            1l.png) → repeat → assemble.
          </div>
          <div style={{ height: 12 }} />
          <div className="muted" style={{ lineHeight: 1.6 }}>
            Tips:
            <div>1. Start with “New Project”.</div>
            <div>2. Keep duration a multiple of 15 for clean segment boundaries.</div>
            <div>3. Upload extracts the last frame immediately; Analyze generates inNB and advances continuity.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
