from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ...nodes.scriptwriter import scriptwriter_node
from ..db import get_session
from ..models import Project, Segment
from ..routes.common import project_to_detail_out
from ..schemas import GenerateWithFeedbackIn, ProjectDetailOut, UpdateFullScriptIn
from ..storage import atomic_write_text, full_script_path
from ..utils import now_utc

router = APIRouter(prefix="/api/projects", tags=["full_script"])


def _invalidate_all_segments(session: Session, project_id: str) -> None:
    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    for s in segs:
        s.status = "pending"
        s.segment_script = ""
        s.video_prompt = ""
        s.video_path = None
        s.video_description = None
        s.last_frame_path = None
        s.updated_at = now_utc()
        session.add(s)


@router.post("/{project_id}/full_script/generate", response_model=ProjectDetailOut)
def generate_full_script(
    project_id: str,
    payload: GenerateWithFeedbackIn,
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Default: regenerate full script invalidates downstream segments.
    _invalidate_all_segments(session, project_id)
    project.canon_summaries = ""
    project.current_segment_index = 0
    project.last_frame_path = None
    project.final_video_path = None

    state = {
        "locale": None,
        "user_prompt": project.user_prompt.strip(),
        "pacing": project.pacing or "",
        "feedback": payload.feedback.strip() if payload.feedback else "",
        "total_duration_seconds": project.total_duration_seconds,
        "segment_duration": project.segment_duration,
    }

    try:
        result = asyncio.run(scriptwriter_node(state))  # type: ignore[arg-type]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Full script generation failed: {str(e)}")

    script = (result.get("full_script") or "").strip()
    if not script:
        raise HTTPException(status_code=500, detail="Empty full_script from model")

    project.full_script = script
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    session.refresh(project)

    atomic_write_text(full_script_path(project_id), script)

    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(project, segs)


@router.put("/{project_id}/full_script", response_model=ProjectDetailOut)
def update_full_script(
    project_id: str,
    payload: UpdateFullScriptIn,
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.full_script = payload.full_script
    project.updated_at = now_utc()

    if payload.invalidate_downstream:
        _invalidate_all_segments(session, project_id)
        project.canon_summaries = ""
        project.current_segment_index = 0
        project.last_frame_path = None
        project.final_video_path = None

    session.add(project)
    session.commit()
    session.refresh(project)

    atomic_write_text(full_script_path(project_id), payload.full_script)

    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(project, segs)
