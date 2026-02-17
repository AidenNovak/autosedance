from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ...clients.doubao import DoubaoClient
from ...config import get_settings
from ...nodes.segmenter import segmenter_node
from ...prompts.loader import get_analyzer_prompts
from ...utils.canon import format_canon_summary
from ...utils.video import extract_last_frame
from ..auth import AuthUser, require_read_user, require_user
from ..authz import require_project_owner
from ..db import get_session
from ..models import Project, Segment
from ..routes.common import project_to_detail_out, segment_to_detail_out
from ..schemas import GenerateWithFeedbackIn, ProjectDetailOut, SegmentDetailOut, UpdateSegmentIn
from ..storage import (
    atomic_write_text,
    frame_path,
    input_video_path,
    segment_txt_path,
)
from ..utils import (
    append_canon,
    canon_before_index,
    export_segment_text,
    now_utc,
    time_range,
    total_segments,
)

router = APIRouter(prefix="/api/projects", tags=["segments"])
logger = logging.getLogger(__name__)


def _get_segment(session: Session, project_id: str, index: int) -> Optional[Segment]:
    stmt = select(Segment).where(Segment.project_id == project_id, Segment.index == index)
    return session.exec(stmt).first()


def _invalidate_downstream_segments(session: Session, project_id: str, index: int) -> None:
    segs = session.exec(
        select(Segment).where(Segment.project_id == project_id, Segment.index > index)
    ).all()
    for s in segs:
        s.status = "pending"
        s.segment_script = ""
        s.video_prompt = ""
        s.video_path = None
        s.video_description = None
        s.last_frame_path = None
        s.updated_at = now_utc()
        session.add(s)


def _latest_frame_before(session: Session, project_id: str, index: int) -> Optional[str]:
    stmt = (
        select(Segment)
        .where(Segment.project_id == project_id, Segment.index < index, Segment.last_frame_path.is_not(None))
        .order_by(Segment.index.desc())
    )
    seg = session.exec(stmt).first()
    return seg.last_frame_path if seg else None


@router.post("/{project_id}/segments/{index}/generate", response_model=ProjectDetailOut)
def generate_segment(
    project_id: str,
    index: int,
    payload: GenerateWithFeedbackIn,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not (project.full_script or "").strip():
        raise HTTPException(status_code=400, detail="full_script is empty; generate it first")

    expected = total_segments(project)
    if index < 0 or index >= expected:
        raise HTTPException(status_code=400, detail=f"index out of range (0..{expected - 1})")

    # Default: regenerating a segment invalidates later segments.
    _invalidate_downstream_segments(session, project_id, index)
    project.canon_summaries = canon_before_index(project.canon_summaries or "", index)
    project.last_frame_path = _latest_frame_before(session, project_id, index)
    project.final_video_path = None

    state = {
        "locale": None,
        "full_script": project.full_script or "",
        "canon_summaries": project.canon_summaries or "",
        "current_segment_index": index,
        "feedback": payload.feedback.strip() if payload.feedback else "",
        "segment_duration": project.segment_duration,
        "total_duration_seconds": project.total_duration_seconds,
    }

    try:
        result = asyncio.run(segmenter_node(state))  # type: ignore[arg-type]
    except Exception:
        logger.exception("Segment generation failed (project_id=%s index=%s)", project_id, index)
        raise HTTPException(status_code=500, detail="Segment generation failed")

    seg_records = result.get("segments") or []
    if not seg_records:
        raise HTTPException(status_code=500, detail="No segment record returned")

    seg_record = seg_records[0]
    seg = _get_segment(session, project_id, index)
    if seg is None:
        seg = Segment(project_id=project_id, index=index)

    seg.segment_script = seg_record.segment_script or ""
    seg.video_prompt = seg_record.video_prompt or ""
    # Regenerating script/prompt implies uploaded video/analysis are stale.
    seg.video_path = None
    seg.video_description = None
    seg.last_frame_path = None
    seg.status = "script_ready"
    seg.updated_at = now_utc()

    session.add(seg)

    # If generating the current segment, move the pointer here.
    project.current_segment_index = index
    project.updated_at = now_utc()
    session.add(project)

    session.commit()
    session.refresh(project)

    atomic_write_text(segment_txt_path(project_id, index), export_segment_text(project, seg))

    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(project, segs)


@router.put("/{project_id}/segments/{index}", response_model=ProjectDetailOut)
def update_segment(
    project_id: str,
    index: int,
    payload: UpdateSegmentIn,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    seg = _get_segment(session, project_id, index)
    if seg is None:
        seg = Segment(project_id=project_id, index=index)

    if payload.segment_script is not None:
        seg.segment_script = payload.segment_script
    if payload.video_prompt is not None:
        seg.video_prompt = payload.video_prompt

    # Editing script/prompt implies uploaded video/analysis are stale.
    if payload.segment_script is not None or payload.video_prompt is not None:
        seg.video_path = None
        seg.video_description = None
        seg.last_frame_path = None

    seg.status = "script_ready"
    seg.updated_at = now_utc()
    session.add(seg)

    if payload.invalidate_downstream:
        _invalidate_downstream_segments(session, project_id, index)
        project.canon_summaries = canon_before_index(project.canon_summaries or "", index)
        project.last_frame_path = _latest_frame_before(session, project_id, index)
        project.final_video_path = None
        project.current_segment_index = index
        project.updated_at = now_utc()
        session.add(project)

    session.commit()
    session.refresh(project)

    atomic_write_text(segment_txt_path(project_id, index), export_segment_text(project, seg))

    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(project, segs)


@router.get("/{project_id}/segments/{index}", response_model=SegmentDetailOut)
def get_segment_detail(
    project_id: str,
    index: int,
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
) -> SegmentDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    seg = _get_segment(session, project_id, index)
    if seg is None:
        # Return a synthetic default segment detail for better UX (segment may not exist yet).
        return SegmentDetailOut(
            index=index,
            segment_script="",
            video_prompt="",
            status="pending",
            video_description=None,
            warnings=[],
            video_path=None,
            last_frame_path=None,
            video_url=None,
            frame_url=None,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    return segment_to_detail_out(project_id, seg)


@router.post("/{project_id}/segments/{index}/video", response_model=SegmentDetailOut)
def upload_segment_video(
    project_id: str,
    index: int,
    file: UploadFile = File(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> SegmentDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    seg = _get_segment(session, project_id, index)
    if seg is None:
        raise HTTPException(status_code=400, detail="Segment not found; generate or create it first")

    # Basic validation (server-side) before writing to disk.
    settings = get_settings()
    allowed_ext = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext and ext not in allowed_ext:
            raise HTTPException(status_code=400, detail="UNSUPPORTED_VIDEO_TYPE")

    dst = input_video_path(project_id, index, original_filename=file.filename)
    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        max_bytes = int(settings.max_upload_mb) * 1024 * 1024
        written = 0
        with dst.open("wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=413, detail="UPLOAD_TOO_LARGE")
                f.write(chunk)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    warnings = []
    # Clear stale frame first; if extraction fails we should not keep an old frame.
    seg.last_frame_path = None
    # Best-effort extract last frame on upload, so the frontend can display it immediately.
    try:
        frame_out = frame_path(project_id, index, ext=".jpg")
        # Avoid leaving a stale frame on disk if extraction fails for the new upload.
        try:
            frame_out.unlink()
        except FileNotFoundError:
            pass
        last_frame = extract_last_frame(str(dst), frame_out)
        seg.last_frame_path = str(last_frame)
    except Exception:
        try:
            frame_out.unlink()
        except Exception:
            pass
        logger.exception("Failed to extract last frame on upload (project_id=%s index=%s)", project_id, index)
        warnings.append("Failed to extract last frame")

    seg.video_path = str(dst)
    seg.video_description = None
    seg.status = "waiting_video"
    seg.updated_at = now_utc()
    session.add(seg)

    # Any change to inputs invalidates prior final assembly.
    project.final_video_path = None
    project.updated_at = now_utc()
    session.add(project)

    session.commit()
    session.refresh(seg)

    return segment_to_detail_out(project_id, seg, warnings=warnings)


@router.get("/{project_id}/segments/{index}/video")
def get_segment_video(
    project_id: str,
    index: int,
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
):
    require_project_owner(session, project_id, user.email)
    seg = _get_segment(session, project_id, index)
    if seg is None or not seg.video_path:
        raise HTTPException(status_code=404, detail="Video not found")
    path = Path(seg.video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")
    return FileResponse(str(path))


@router.post("/{project_id}/segments/{index}/extract_frame", response_model=SegmentDetailOut)
def extract_segment_frame(
    project_id: str,
    index: int,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> SegmentDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    seg = _get_segment(session, project_id, index)
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    if not seg.video_path:
        raise HTTPException(status_code=400, detail="Segment has no uploaded video")

    video_path = Path(seg.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Uploaded video path missing on disk")

    warnings = []
    try:
        frame_out = frame_path(project_id, index, ext=".jpg")
        last_frame = extract_last_frame(str(video_path), frame_out)
        seg.last_frame_path = str(last_frame)
    except Exception:
        logger.exception("Failed to extract last frame (project_id=%s index=%s)", project_id, index)
        warnings.append("Failed to extract last frame")

    seg.updated_at = now_utc()
    session.add(seg)
    session.commit()
    session.refresh(seg)

    return segment_to_detail_out(project_id, seg, warnings=warnings)


@router.post("/{project_id}/segments/{index}/analyze", response_model=ProjectDetailOut)
def analyze_segment(
    project_id: str,
    index: int,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    seg = _get_segment(session, project_id, index)
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    if not seg.video_path:
        raise HTTPException(status_code=400, detail="Segment has no uploaded video")
    if not Path(seg.video_path).exists():
        raise HTTPException(status_code=400, detail="Uploaded video path missing on disk")

    seg.status = "analyzing"
    seg.updated_at = now_utc()
    session.add(seg)
    session.commit()
    session.refresh(seg)

    # Extract last frame
    frame_out = frame_path(project_id, index, ext=".jpg")
    try:
        last_frame = extract_last_frame(seg.video_path, frame_out)
    except Exception:
        seg.status = "failed"
        seg.updated_at = now_utc()
        session.add(seg)
        session.commit()
        logger.exception("Failed to extract frame (project_id=%s index=%s)", project_id, index)
        raise HTTPException(status_code=500, detail="Failed to extract frame")

    start, end = time_range(project, index)

    # Multimodal analysis
    client = DoubaoClient()
    try:
        prompts = get_analyzer_prompts(None)
        description = asyncio.run(
            client.chat_with_image(
                system_prompt=prompts.system,
                user_message=prompts.user.format(
                    segment_script=seg.segment_script,
                    time_range=f"{start}s-{end}s",
                ),
                image_path=str(last_frame),
            )
        )
    except Exception:
        seg.status = "failed"
        seg.updated_at = now_utc()
        session.add(seg)
        session.commit()
        logger.exception("Video analysis failed (project_id=%s index=%s)", project_id, index)
        raise HTTPException(status_code=500, detail="Video analysis failed")

    seg.video_description = description
    seg.last_frame_path = str(last_frame)
    seg.status = "completed"
    seg.updated_at = now_utc()
    session.add(seg)

    summary = format_canon_summary(index, start, end, description)
    project.canon_summaries = append_canon(project.canon_summaries or "", summary)
    project.last_frame_path = seg.last_frame_path
    project.current_segment_index = index + 1
    project.final_video_path = None
    project.updated_at = now_utc()
    session.add(project)

    session.commit()
    session.refresh(project)

    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(project, segs)


@router.get("/{project_id}/segments/{index}/frame")
def get_segment_frame(
    project_id: str,
    index: int,
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
):
    require_project_owner(session, project_id, user.email)
    seg = _get_segment(session, project_id, index)
    if seg is None or not seg.last_frame_path:
        raise HTTPException(status_code=404, detail="Frame not found")
    path = Path(seg.last_frame_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Frame file missing on disk")
    return FileResponse(str(path))


@router.get("/{project_id}/segments/{index}/frame/download")
def download_segment_frame(
    project_id: str,
    index: int,
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
):
    """Force-download the frame (no CORS/fetch needed on the frontend)."""
    require_project_owner(session, project_id, user.email)
    seg = _get_segment(session, project_id, index)
    if seg is None or not seg.last_frame_path:
        raise HTTPException(status_code=404, detail="Frame not found")
    path = Path(seg.last_frame_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Frame file missing on disk")

    ext = path.suffix if path.suffix else ".jpg"
    filename = f"frame_{index + 1:03d}{ext}"
    return FileResponse(str(path), filename=filename)
