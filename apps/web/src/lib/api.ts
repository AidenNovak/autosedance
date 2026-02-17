export type SegmentSummary = {
  index: number;
  status: string;
  has_video: boolean;
  has_frame: boolean;
  has_description: boolean;
  updated_at: string;
  video_url?: string | null;
  frame_url?: string | null;
};

export type SegmentDetail = {
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
  created_at: string;
  updated_at: string;
};

export type ProjectSummary = {
  id: string;
  user_prompt: string;
  pacing: string;
  total_duration_seconds: number;
  segment_duration: number;
  current_segment_index: number;
  created_at: string;
  updated_at: string;
  num_segments: number;
  next_action: string;
  segments_completed: number;
  segments_with_video: number;
  segments_with_frame: number;
  segments_with_description: number;
};

export type ProjectDetail = {
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
  segments: SegmentSummary[];
};

export type Job = {
  id: string;
  project_id: string;
  type: "full_script" | "segment_generate" | "extract_frame" | "analyze" | "assemble";
  status: "queued" | "running" | "succeeded" | "failed" | "canceled";
  progress: number;
  message: string;
  error?: string | null;
  payload: Record<string, any>;
  result: Record<string, any>;
  created_at: string;
  updated_at: string;
};

// Convenience aliases for older imports.
export type Project = ProjectDetail;
export type Segment = SegmentDetail;

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

export async function listProjects(): Promise<ProjectSummary[]> {
  return req<ProjectSummary[]>("/api/projects");
}

export async function createProject(input: {
  user_prompt: string;
  total_duration_seconds: number;
  segment_duration?: number;
  pacing?: "normal" | "slow" | "urgent";
}): Promise<ProjectDetail> {
  return req<ProjectDetail>("/api/projects", {
    method: "POST",
    body: JSON.stringify({
      segment_duration: 15,
      pacing: "normal",
      ...input
    })
  });
}

export async function getProject(
  projectId: string,
  opts?: { include_full_script?: boolean; include_canon?: boolean }
): Promise<ProjectDetail> {
  const include_full_script = opts?.include_full_script ?? true;
  const include_canon = opts?.include_canon ?? true;
  return req<ProjectDetail>(
    `/api/projects/${projectId}?include_full_script=${include_full_script ? "true" : "false"}&include_canon=${
      include_canon ? "true" : "false"
    }`
  );
}

export async function getSegment(projectId: string, index: number): Promise<SegmentDetail> {
  return req<SegmentDetail>(`/api/projects/${projectId}/segments/${index}`);
}

export async function generateFullScript(projectId: string, feedback?: string): Promise<ProjectDetail> {
  return req<ProjectDetail>(`/api/projects/${projectId}/full_script/generate`, {
    method: "POST",
    body: JSON.stringify({ feedback: feedback || null })
  });
}

export async function updateFullScript(projectId: string, full_script: string, invalidate_downstream = true) {
  return req<ProjectDetail>(`/api/projects/${projectId}/full_script`, {
    method: "PUT",
    body: JSON.stringify({ full_script, invalidate_downstream })
  });
}

export async function generateSegment(projectId: string, index: number, feedback?: string): Promise<ProjectDetail> {
  return req<ProjectDetail>(`/api/projects/${projectId}/segments/${index}/generate`, {
    method: "POST",
    body: JSON.stringify({ feedback: feedback || null })
  });
}

export async function updateSegment(
  projectId: string,
  index: number,
  patch: { segment_script?: string; video_prompt?: string; invalidate_downstream?: boolean }
): Promise<ProjectDetail> {
  return req<ProjectDetail>(`/api/projects/${projectId}/segments/${index}`, {
    method: "PUT",
    body: JSON.stringify({ invalidate_downstream: true, ...patch })
  });
}

export async function uploadVideo(projectId: string, index: number, file: File): Promise<SegmentDetail> {
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
  return (await res.json()) as SegmentDetail;
}

export async function extractFrame(projectId: string, index: number): Promise<SegmentDetail> {
  return req<SegmentDetail>(`/api/projects/${projectId}/segments/${index}/extract_frame`, {
    method: "POST"
  });
}

export async function analyzeSegment(projectId: string, index: number): Promise<ProjectDetail> {
  return req<ProjectDetail>(`/api/projects/${projectId}/segments/${index}/analyze`, {
    method: "POST"
  });
}

export async function assemble(projectId: string): Promise<ProjectDetail> {
  return req<ProjectDetail>(`/api/projects/${projectId}/assemble`, { method: "POST" });
}

export async function createJob(
  projectId: string,
  input: { type: Job["type"]; index?: number; feedback?: string; locale?: string }
): Promise<Job> {
  return req<Job>(`/api/projects/${projectId}/jobs`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function getJob(projectId: string, jobId: string): Promise<Job> {
  return req<Job>(`/api/projects/${projectId}/jobs/${jobId}`);
}

export function backendUrl(): string {
  return BASE;
}
