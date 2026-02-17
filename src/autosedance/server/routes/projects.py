from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ...utils.video import concatenate_videos
from ..auth import AuthUser, require_read_user, require_user
from ..authz import require_project_owner
from ..db import get_session
from ..models import Project, ProjectOwner, Segment
from ..routes.common import project_to_detail_out, project_to_summary_out
from ..schemas import CreateProjectIn, ProjectDetailOut, ProjectSummaryOut
from ..storage import ensure_project_dirs, final_video_path
from ..utils import now_utc, total_segments

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ProjectDetailOut)
def create_project(
    payload: CreateProjectIn,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
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
    if user.email:
        session.add(ProjectOwner(project_id=project.id, email=user.email, created_at=now_utc()))
        session.commit()

    segments: List[Segment] = []
    return project_to_detail_out(project, segments)


@router.get("", response_model=List[ProjectSummaryOut])
def list_projects(
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
) -> List[ProjectSummaryOut]:
    if user.email:
        owners = session.exec(select(ProjectOwner).where(ProjectOwner.email == user.email)).all()
        ids = [o.project_id for o in owners]
        if not ids:
            return []
        projects = session.exec(select(Project).where(Project.id.in_(ids)).order_by(Project.created_at.desc())).all()
    else:
        projects = session.exec(select(Project).order_by(Project.created_at.desc())).all()
    if not projects:
        return []

    ids = [p.id for p in projects]
    segs = session.exec(select(Segment).where(Segment.project_id.in_(ids))).all()
    by_project: dict[str, List[Segment]] = {pid: [] for pid in ids}
    for s in segs:
        by_project.setdefault(s.project_id, []).append(s)

    return [project_to_summary_out(p, by_project.get(p.id, [])) for p in projects]


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(
    project_id: str,
    include_full_script: bool = True,
    include_canon: bool = True,
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(
        project,
        segs,
        include_full_script=include_full_script,
        include_canon=include_canon,
    )


@router.post("/{project_id}/assemble", response_model=ProjectDetailOut)
def assemble_project(
    project_id: str,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ProjectDetailOut:
    require_project_owner(session, project_id, user.email)
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
    except Exception:
        logger.exception("Video assembly failed (project_id=%s)", project_id)
        raise HTTPException(status_code=500, detail="Video assembly failed")

    project.final_video_path = str(Path(final_path))
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    session.refresh(project)

    # Refresh segments for response
    segs = session.exec(select(Segment).where(Segment.project_id == project_id)).all()
    return project_to_detail_out(project, segs)


@router.get("/{project_id}/final")
def get_final_video(
    project_id: str,
    user: AuthUser = Depends(require_read_user),
    session: Session = Depends(get_session),
):
    require_project_owner(session, project_id, user.email)
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.final_video_path:
        raise HTTPException(status_code=404, detail="Final video not found")

    path = Path(project.final_video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Final video file missing on disk")
    return FileResponse(str(path))
