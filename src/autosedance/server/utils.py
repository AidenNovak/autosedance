from __future__ import annotations

from datetime import datetime
import re
from typing import List, Tuple

from .models import Project, Segment


def total_segments(project: Project) -> int:
    d = int(project.total_duration_seconds)
    seg = int(project.segment_duration or 15)
    return (d + seg - 1) // seg


def time_range(project: Project, index: int) -> Tuple[int, int]:
    seg = int(project.segment_duration or 15)
    start = index * seg
    end = min((index + 1) * seg, int(project.total_duration_seconds))
    return start, end


def split_canon(canon_summaries: str) -> List[str]:
    canon_summaries = canon_summaries or ""
    parts = [p.strip() for p in canon_summaries.split("\n---\n") if p.strip()]
    return parts


def canon_recent(canon_summaries: str, keep: int = 3) -> str:
    parts = split_canon(canon_summaries)
    if not parts:
        return "尚未生成任何片段"
    return "\n---\n".join(parts[-keep:])


def append_canon(canon_summaries: str, summary: str) -> str:
    canon_summaries = canon_summaries or ""
    summary = (summary or "").strip()
    if not summary:
        return canon_summaries
    if not canon_summaries.strip():
        return summary
    return f"{canon_summaries}\n---\n{summary}"


def canon_before_index(canon_summaries: str, index: int) -> str:
    """Keep only canon summary items for segments strictly before `index`."""
    kept: List[str] = []
    for item in split_canon(canon_summaries or ""):
        m = re.match(r"^片段(\d+)\(", item)
        if m:
            if int(m.group(1)) < index:
                kept.append(item)
        else:
            # If the item doesn't match our format, keep it to avoid data loss.
            kept.append(item)
    return "\n---\n".join(kept)


def now_utc() -> datetime:
    return datetime.utcnow()


def export_segment_text(project: Project, segment: Segment) -> str:
    start, end = time_range(project, segment.index)
    return (
        f"# 片段 {segment.index}\n\n"
        f"## 时间范围\n{start}s - {end}s\n\n"
        f"## 剧本（给人看）\n{segment.segment_script}\n\n"
        f"## 视频Prompt（给视频生成模型/人工参考）\n{segment.video_prompt}\n\n"
        f"---\n生成时间: {now_utc().isoformat()}Z\n"
    )


def derive_next_action(project: Project, segments: List[Segment]) -> str:
    if not (project.full_script or "").strip():
        return "generate_full_script"

    expected = total_segments(project)
    idx = int(project.current_segment_index or 0)
    if idx < 0:
        idx = 0
    if idx >= expected:
        # All segments should be done; next is assemble/done.
        if not project.final_video_path:
            return "assemble"
        return "done"

    by_index = {s.index: s for s in segments}
    seg = by_index.get(idx)
    if seg is None or seg.status == "pending":
        return "generate_segment"
    if seg.status in ("script_ready",):
        return "upload_video" if not seg.video_path else "analyze"
    if seg.status in ("waiting_video",):
        return "analyze" if seg.video_path else "upload_video"
    if seg.status == "analyzing":
        return "wait_analyze"
    if seg.status == "completed":
        return "generate_segment"
    if seg.status == "failed":
        return "retry"
    return "unknown"
