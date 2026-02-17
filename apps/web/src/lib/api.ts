export type Segment = {
  index: number;
  segment_script: string;
  video_prompt: string;
  status: string;
  video_description?: string | null;
  warnings?: string[] | null;
  video_path?: string | null;
  last_frame_path?: string | null;
  video_url?: string | null;
  frame_url?: string | null;
};

export type Project = {
  id: string;
  user_prompt: string;
  pacing: string;
  total_duration_seconds: number;
  segment_duration: number;
  full_script?: string | null;
  canon_summaries: string;
  current_segment_index: number;
  last_frame_path?: string | null;
  final_video_path?: string | null;
  created_at: string;
  updated_at: string;
  num_segments: number;
  next_action: string;
  segments: Segment[];
};

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" })
    },
    cache: "no-store"
  });

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return (await res.json()) as T;
}

export async function listProjects(): Promise<Project[]> {
  return req<Project[]>("/api/projects");
}

export async function createProject(input: {
  user_prompt: string;
  total_duration_seconds: number;
  segment_duration?: number;
  pacing?: "normal" | "slow" | "urgent";
}): Promise<Project> {
  return req<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify({
      segment_duration: 15,
      pacing: "normal",
      ...input
    })
  });
}

export async function getProject(projectId: string): Promise<Project> {
  return req<Project>(`/api/projects/${projectId}`);
}

export async function generateFullScript(projectId: string, feedback?: string): Promise<Project> {
  return req<Project>(`/api/projects/${projectId}/full_script/generate`, {
    method: "POST",
    body: JSON.stringify({ feedback: feedback || null })
  });
}

export async function updateFullScript(projectId: string, full_script: string, invalidate_downstream = true) {
  return req<Project>(`/api/projects/${projectId}/full_script`, {
    method: "PUT",
    body: JSON.stringify({ full_script, invalidate_downstream })
  });
}

export async function generateSegment(projectId: string, index: number, feedback?: string): Promise<Project> {
  return req<Project>(`/api/projects/${projectId}/segments/${index}/generate`, {
    method: "POST",
    body: JSON.stringify({ feedback: feedback || null })
  });
}

export async function updateSegment(
  projectId: string,
  index: number,
  patch: { segment_script?: string; video_prompt?: string; invalidate_downstream?: boolean }
): Promise<Project> {
  return req<Project>(`/api/projects/${projectId}/segments/${index}`, {
    method: "PUT",
    body: JSON.stringify({ invalidate_downstream: true, ...patch })
  });
}

export async function uploadVideo(projectId: string, index: number, file: File): Promise<Segment> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/projects/${projectId}/segments/${index}/video`, {
    method: "POST",
    body: form,
    cache: "no-store"
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as Segment;
}

export async function extractFrame(projectId: string, index: number): Promise<Segment> {
  return req<Segment>(`/api/projects/${projectId}/segments/${index}/extract_frame`, {
    method: "POST"
  });
}

export async function analyzeSegment(projectId: string, index: number): Promise<Project> {
  return req<Project>(`/api/projects/${projectId}/segments/${index}/analyze`, {
    method: "POST"
  });
}

export async function assemble(projectId: string): Promise<Project> {
  return req<Project>(`/api/projects/${projectId}/assemble`, { method: "POST" });
}

export function backendUrl(): string {
  return BASE;
}
