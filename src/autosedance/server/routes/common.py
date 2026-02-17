from __future__ import annotations

from typing import List, Optional

from ..models import Project, Segment
from ..schemas import ProjectDetailOut, ProjectSummaryOut, SegmentDetailOut, SegmentSummaryOut
from ..utils import derive_next_action, total_segments


def segment_to_detail_out(
    project_id: str, segment: Segment, warnings: Optional[List[str]] = None
) -> SegmentDetailOut:
    video_url: Optional[str] = None
    frame_url: Optional[str] = None
    if segment.video_path:
        video_url = f"/api/projects/{project_id}/segments/{segment.index}/video"
    if segment.last_frame_path:
        frame_url = f"/api/projects/{project_id}/segments/{segment.index}/frame"

    return SegmentDetailOut(
        index=segment.index,
        segment_script=segment.segment_script or "",
        video_prompt=segment.video_prompt or "",
        status=segment.status,
        video_description=segment.video_description,
        warnings=warnings or [],
        video_path=segment.video_path,
        last_frame_path=segment.last_frame_path,
        video_url=video_url,
        frame_url=frame_url,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


def segment_to_summary_out(project_id: str, segment: Segment) -> SegmentSummaryOut:
    video_url: Optional[str] = None
    frame_url: Optional[str] = None
    if segment.video_path:
        video_url = f"/api/projects/{project_id}/segments/{segment.index}/video"
    if segment.last_frame_path:
        frame_url = f"/api/projects/{project_id}/segments/{segment.index}/frame"

    return SegmentSummaryOut(
        index=segment.index,
        status=segment.status,
        has_video=bool(segment.video_path),
        has_frame=bool(segment.last_frame_path),
        has_description=bool(segment.video_description),
        updated_at=segment.updated_at,
        video_url=video_url,
        frame_url=frame_url,
    )


def project_to_detail_out(
    project: Project,
    segments: List[Segment],
    *,
    include_full_script: bool = True,
    include_canon: bool = True,
) -> ProjectDetailOut:
    segs_sorted = sorted(segments, key=lambda s: s.index)
    expected = total_segments(project)
    by_index = {s.index: s for s in segs_sorted}
    segments_summary: List[SegmentSummaryOut] = []
    for i in range(expected):
        seg = by_index.get(i)
        if seg is None:
            segments_summary.append(
                SegmentSummaryOut(
                    index=i,
                    status="pending",
                    has_video=False,
                    has_frame=False,
                    has_description=False,
                    updated_at=project.updated_at,
                    video_url=None,
                    frame_url=None,
                )
            )
        else:
            segments_summary.append(segment_to_summary_out(project.id, seg))
    return ProjectDetailOut(
        id=project.id,
        user_prompt=project.user_prompt,
        pacing=project.pacing,
        total_duration_seconds=project.total_duration_seconds,
        segment_duration=project.segment_duration,
        full_script=project.full_script if include_full_script else None,
        canon_summaries=project.canon_summaries or "" if include_canon else "",
        current_segment_index=project.current_segment_index or 0,
        last_frame_path=project.last_frame_path,
        final_video_path=project.final_video_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
        num_segments=total_segments(project),
        next_action=derive_next_action(project, segs_sorted),
        segments=segments_summary,
    )


def project_to_summary_out(project: Project, segments: List[Segment]) -> ProjectSummaryOut:
    segs_sorted = sorted(segments, key=lambda s: s.index)
    completed = sum(1 for s in segs_sorted if s.status == "completed")
    with_video = sum(1 for s in segs_sorted if s.video_path)
    with_frame = sum(1 for s in segs_sorted if s.last_frame_path)
    with_description = sum(1 for s in segs_sorted if s.video_description)

    return ProjectSummaryOut(
        id=project.id,
        user_prompt=project.user_prompt,
        pacing=project.pacing,
        total_duration_seconds=project.total_duration_seconds,
        segment_duration=project.segment_duration,
        current_segment_index=project.current_segment_index or 0,
        created_at=project.created_at,
        updated_at=project.updated_at,
        num_segments=total_segments(project),
        next_action=derive_next_action(project, segs_sorted),
        segments_completed=completed,
        segments_with_video=with_video,
        segments_with_frame=with_frame,
        segments_with_description=with_description,
    )


# Backwards compatible aliases.
segment_to_out = segment_to_detail_out
project_to_out = project_to_detail_out
