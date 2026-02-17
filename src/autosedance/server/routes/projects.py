from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ...utils.video import concatenate_videos
from ..db import get_session
from ..models import Project, Segment
from ..routes.common import project_to_out
from ..schemas import CreateProjectIn, ProjectOut
from ..storage import ensure_project_dirs, final_video_path
from ..utils import now_utc, total_segments

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(payload: CreateProjectIn, session: Session = Depends(get_session)) -> ProjectOut:
    if payload.total_duration_seconds <= 0:
        raise HTTPException(status_code=400, detail="total_duration_seconds must be > 0")
    if payload.segment_duration <= 0:
        raise HTTPException(status_code=400, detail="segment_duration must be > 0")

    project = Project(
        user_prompt=payload.user_prompt,
        pacing=payload.pacing,
        total_duration_seconds=payload.total_duration_seconds,
        segment_duration=payload.segment_duration,
        full_script=None,
        canon_summaries="",
        current_segment_index=0,
        last_frame_path=None,
        final_video_path=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    ensure_project_dirs(project.id)

    segments: List[Segment] = []
    return project_to_out(project, segments)


@router.get("", response_model=List[ProjectOut])
def list_projects(session: Session = Depends(get_session)) -> List[ProjectOut]:
    projects = session.exec(select(Project).order_by(Project.created_at.desc())).all()
    out: List[ProjectOut] = []
    for p in projects:
        segs = session.exec(select(Segment).where(Segment.project_id == p.id)).all()
        out.append(project_to_out(p, segs))
    return out


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, session: Session = Depends(get_session)) -> ProjectOut:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_out(project, segs)


@router.post("/{project_id}/assemble", response_model=ProjectOut)
def assemble_project(project_id: str, session: Session = Depends(get_session)) -> ProjectOut:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    expected = total_segments(project)
    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    segs_sorted = sorted(segs, key=lambda s: s.index)

    by_index = {s.index: s for s in segs_sorted}
    missing = [i for i in range(expected) if i not in by_index or not by_index[i].video_path]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing videos for segments: {missing}")

    video_paths = [by_index[i].video_path for i in range(expected)]  # type: ignore[list-item]
    output_path = final_video_path(project_id)

    try:
        final_path = asyncio.run(concatenate_videos(video_paths, output_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video assembly failed: {str(e)}")

    project.final_video_path = str(Path(final_path))
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    session.refresh(project)

    # Refresh segments for response
    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_out(project, segs)


@router.get("/{project_id}/final")
def get_final_video(project_id: str, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.final_video_path:
        raise HTTPException(status_code=404, detail="Final video not found")

    path = Path(project.final_video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Final video file missing on disk")
    return FileResponse(str(path))
