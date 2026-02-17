from __future__ import annotations

from typing import List, Optional

from ..models import Project, Segment
from ..schemas import ProjectOut, SegmentOut
from ..utils import derive_next_action, total_segments


def segment_to_out(project_id: str, segment: Segment) -> SegmentOut:
    video_url: Optional[str] = None
    frame_url: Optional[str] = None
    if segment.video_path:
        video_url = f"/api/projects/{project_id}/segments/{segment.index}/video"
    if segment.last_frame_path:
        frame_url = f"/api/projects/{project_id}/segments/{segment.index}/frame"

    return SegmentOut(
        index=segment.index,
        segment_script=segment.segment_script or "",
        video_prompt=segment.video_prompt or "",
        status=segment.status,
        video_description=segment.video_description,
        video_path=segment.video_path,
        last_frame_path=segment.last_frame_path,
        video_url=video_url,
        frame_url=frame_url,
    )


def project_to_out(project: Project, segments: List[Segment]) -> ProjectOut:
    segs_sorted = sorted(segments, key=lambda s: s.index)
    return ProjectOut(
        id=project.id,
        user_prompt=project.user_prompt,
        pacing=project.pacing,
        total_duration_seconds=project.total_duration_seconds,
        segment_duration=project.segment_duration,
        full_script=project.full_script,
        canon_summaries=project.canon_summaries or "",
        current_segment_index=project.current_segment_index or 0,
        last_frame_path=project.last_frame_path,
        final_video_path=project.final_video_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
        num_segments=total_segments(project),
        next_action=derive_next_action(project, segs_sorted),
        segments=[segment_to_out(project.id, s) for s in segs_sorted],
    )

