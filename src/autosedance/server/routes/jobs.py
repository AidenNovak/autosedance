from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Job, Project
from ..schemas import CreateJobIn, JobOut
from ..utils import now_utc

router = APIRouter(prefix="/api/projects", tags=["jobs"])


def _job_to_out(job: Job) -> JobOut:
    try:
        payload = json.loads(job.payload_json or "{}")
    except Exception:
        payload = {}
    try:
        result = json.loads(job.result_json or "{}")
    except Exception:
        result = {}

    return JobOut(
        id=job.id,
        project_id=job.project_id,
        type=job.type,  # type: ignore[arg-type]
        status=job.status,  # type: ignore[arg-type]
        progress=int(job.progress or 0),
        message=job.message or "",
        error=job.error,
        payload=payload,
        result=result,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/{project_id}/jobs", response_model=JobOut)
def create_job(
    project_id: str,
    payload: CreateJobIn,
    session: Session = Depends(get_session),
) -> JobOut:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    data = payload.model_dump()
    job = Job(
        project_id=project_id,
        type=data["type"],
        status="queued",
        progress=0,
        message="queued",
        error=None,
        payload_json=json.dumps(data, ensure_ascii=False),
        result_json="{}",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_to_out(job)


@router.get("/{project_id}/jobs", response_model=List[JobOut])
def list_jobs(
    project_id: str,
    limit: int = 20,
    session: Session = Depends(get_session),
) -> List[JobOut]:
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    jobs = session.exec(
        select(Job)
        .where(Job.project_id == project_id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    ).all()
    return [_job_to_out(j) for j in jobs]


@router.get("/{project_id}/jobs/{job_id}", response_model=JobOut)
def get_job(
    project_id: str,
    job_id: str,
    session: Session = Depends(get_session),
) -> JobOut:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = session.get(Job, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Job not found")

    return _job_to_out(job)

