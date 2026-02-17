"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { createProject } from "@/lib/api";

const DURATIONS = [30, 45, 60, 75, 90, 120, 180];

export default function NewProjectPage() {
  const router = useRouter();

  const [duration, setDuration] = useState<number>(60);
  const [pacing, setPacing] = useState<"normal" | "slow" | "urgent">("normal");
  const [prompt, setPrompt] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const durationHint = useMemo(() => {
    if (duration % 15 === 0) return "ok";
    return `Will be split into 15s chunks; last chunk will be shorter (${duration % 15}s remainder).`;
  }, [duration]);

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
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid two">
      <div className="card">
        <div className="hd">
          <h2>New Project</h2>
          <span className="pill">manual upload mode</span>
        </div>
        <div className="bd">
          <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Total Duration (seconds)</div>
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
                <span className="pill">segment=15s</span>
              </div>
              <div className="muted" style={{ fontSize: 13 }}>
                {durationHint === "ok" ? <span style={{ color: "var(--ok)" }}>multiple of 15</span> : durationHint}
              </div>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Pacing</div>
              <select className="select" value={pacing} onChange={(e) => setPacing(e.target.value as any)}>
                <option value="normal">normal</option>
                <option value="slow">slow</option>
                <option value="urgent">urgent</option>
              </select>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <div className="muted">Prompt</div>
              <textarea
                className="textarea"
                placeholder="Describe your story, style, characters, constraints…"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                required
              />
            </div>

            {error ? <div style={{ color: "var(--danger)" }}>{error}</div> : null}

            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn primary" type="submit" disabled={loading}>
                {loading ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="hd">
          <h2>What You Get</h2>
        </div>
        <div className="bd">
          <div className="muted" style={{ lineHeight: 1.7 }}>
            <div>1. in0: minute-level full script</div>
            <div>2. inN: 15s segment script + video prompt</div>
            <div>3. Upload: you provide the actual video file</div>
            <div>4. inNB: model describes last frame + continuity notes</div>
            <div>5. Assemble: ffmpeg concat into a final mp4</div>
          </div>
        </div>
      </div>
    </div>
  );
}

