from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from ..clients.doubao import DoubaoClient
from ..nodes.scriptwriter import scriptwriter_node
from ..nodes.segmenter import segmenter_node
from ..prompts.loader import get_analyzer_prompts
from ..utils.canon import format_canon_summary
from ..utils.video import concatenate_videos, extract_last_frame
from .db import get_engine
from .models import Job, Project, Segment
from .storage import (
    atomic_write_text,
    final_video_path as final_video_path_for_project,
    frame_path as frame_path_for_segment,
    full_script_path as full_script_path_for_project,
    segment_txt_path,
)
from .utils import (
    append_canon,
    canon_before_index,
    canon_recent,
    export_segment_text,
    now_utc,
    time_range,
    total_segments,
)

_thread: Optional[threading.Thread] = None
_stop = threading.Event()


def start_worker() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="autosedance-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    _stop.set()


def _job_payload(job: Job) -> dict:
    try:
        return json.loads(job.payload_json or "{}")
    except Exception:
        return {}


def _job_result(job: Job) -> dict:
    try:
        data = json.loads(job.result_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _ui_message(key: str, params: Optional[dict] = None) -> dict:
    msg: dict = {"key": key}
    if params:
        msg["params"] = params
    return {"ui_message": msg}


def _set_job(
    session: Session,
    job: Job,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    result: Optional[dict] = None,
) -> None:
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = int(progress)
    if message is not None:
        job.message = message
    if error is not None:
        job.error = error
    if result is not None:
        # Merge structured result fields (for example, ui_message) so incremental
        # updates don't clobber earlier data.
        cur = _job_result(job)
        cur.update(result)
        job.result_json = json.dumps(cur, ensure_ascii=False)
    job.updated_at = now_utc()
    session.add(job)
    session.commit()
    session.refresh(job)


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
    session.commit()


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
    session.commit()


def _latest_frame_before(session: Session, project_id: str, index: int) -> Optional[str]:
    stmt = (
        select(Segment)
        .where(
            Segment.project_id == project_id,
            Segment.index < index,
            Segment.last_frame_path.is_not(None),
        )
        .order_by(Segment.index.desc())
        .limit(1)
    )
    seg = session.exec(stmt).first()
    return seg.last_frame_path if seg else None


def _run_full_script_job(session: Session, job: Job) -> dict:
    payload = _job_payload(job)
    project = session.get(Project, job.project_id)
    if not project:
        raise RuntimeError("Project not found")

    _set_job(
        session,
        job,
        progress=5,
        message="Invalidating segments",
        result=_ui_message("jobmsg.full_script.invalidating"),
    )
    _invalidate_all_segments(session, job.project_id)

    project.canon_summaries = ""
    project.current_segment_index = 0
    project.last_frame_path = None
    project.final_video_path = None
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    session.refresh(project)

    user_prompt = project.user_prompt.strip()
    feedback = (payload.get("feedback") or "").strip()
    state = {
        "locale": payload.get("locale"),
        "user_prompt": user_prompt,
        "pacing": project.pacing or "",
        "feedback": feedback,
        "total_duration_seconds": project.total_duration_seconds,
        "segment_duration": project.segment_duration,
    }

    _set_job(
        session,
        job,
        progress=20,
        message="Calling LLM (full script)",
        result=_ui_message("jobmsg.full_script.calling_llm"),
    )
    result = asyncio.run(scriptwriter_node(state))  # type: ignore[arg-type]
    script = (result.get("full_script") or "").strip()
    if not script:
        raise RuntimeError("Empty full_script from model")

    project.full_script = script
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    session.refresh(project)

    _set_job(
        session,
        job,
        progress=90,
        message="Writing full_script.txt",
        result=_ui_message("jobmsg.full_script.writing"),
    )
    atomic_write_text(full_script_path_for_project(project.id), script)
    return {"full_script_len": len(script)}


def _run_segment_generate_job(session: Session, job: Job) -> dict:
    payload = _job_payload(job)
    idx = payload.get("index")
    if idx is None:
        raise RuntimeError("Missing index for segment_generate")
    idx = int(idx)
    seg_n = f"{idx + 1:03d}"

    project = session.get(Project, job.project_id)
    if not project:
        raise RuntimeError("Project not found")
    if not (project.full_script or "").strip():
        raise RuntimeError("full_script is empty; generate it first")

    expected = total_segments(project)
    if idx < 0 or idx >= expected:
        raise RuntimeError(f"index out of range (0..{expected - 1})")

    _set_job(
        session,
        job,
        progress=5,
        message="Invalidating downstream segments",
        result=_ui_message("jobmsg.segment.invalidating", {"n": seg_n}),
    )
    _invalidate_downstream_segments(session, project.id, idx)

    project.canon_summaries = canon_before_index(project.canon_summaries or "", idx)
    project.last_frame_path = _latest_frame_before(session, project.id, idx)
    project.final_video_path = None
    project.current_segment_index = idx
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    session.refresh(project)

    full_script = project.full_script or ""
    feedback = (payload.get("feedback") or "").strip()

    state = {
        "locale": payload.get("locale"),
        "full_script": full_script,
        "canon_summaries": canon_recent(project.canon_summaries or "", keep=3),
        "current_segment_index": idx,
        "feedback": feedback,
        "segment_duration": project.segment_duration,
        "total_duration_seconds": project.total_duration_seconds,
    }

    _set_job(
        session,
        job,
        progress=20,
        message=f"Calling LLM (segment {idx + 1})",
        result=_ui_message("jobmsg.segment.calling_llm", {"n": seg_n}),
    )
    result = asyncio.run(segmenter_node(state))  # type: ignore[arg-type]
    seg_records = result.get("segments") or []
    if not seg_records:
        raise RuntimeError("No segment record returned")

    seg_record = seg_records[0]
    seg = session.exec(
        select(Segment).where(Segment.project_id == project.id, Segment.index == idx)
    ).first()
    if seg is None:
        seg = Segment(project_id=project.id, index=idx, created_at=now_utc(), updated_at=now_utc())

    seg.segment_script = seg_record.segment_script or ""
    seg.video_prompt = seg_record.video_prompt or ""
    seg.video_path = None
    seg.video_description = None
    seg.last_frame_path = None
    seg.status = "script_ready"
    seg.updated_at = now_utc()
    session.add(seg)
    session.commit()
    session.refresh(seg)

    _set_job(
        session,
        job,
        progress=90,
        message="Writing segment txt",
        result=_ui_message("jobmsg.segment.writing", {"n": seg_n}),
    )
    atomic_write_text(segment_txt_path(project.id, idx), export_segment_text(project, seg))
    return {"index": idx}


def _run_extract_frame_job(session: Session, job: Job) -> dict:
    payload = _job_payload(job)
    idx = payload.get("index")
    if idx is None:
        raise RuntimeError("Missing index for extract_frame")
    idx = int(idx)
    seg_n = f"{idx + 1:03d}"

    seg = session.exec(
        select(Segment).where(Segment.project_id == job.project_id, Segment.index == idx)
    ).first()
    if seg is None or not seg.video_path:
        raise RuntimeError("Segment or video not found")
    video_path = Path(seg.video_path)
    if not video_path.exists():
        raise RuntimeError("Uploaded video missing on disk")

    _set_job(
        session,
        job,
        progress=30,
        message="Extracting last frame",
        result=_ui_message("jobmsg.extract_frame.extracting", {"n": seg_n}),
    )
    out = frame_path_for_segment(job.project_id, idx, ext=".jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.unlink()
    except FileNotFoundError:
        pass
    frame = extract_last_frame(str(video_path), out)
    seg.last_frame_path = str(frame)
    seg.updated_at = now_utc()
    session.add(seg)
    session.commit()
    return {"index": idx, "last_frame_path": str(frame)}


def _run_analyze_job(session: Session, job: Job) -> dict:
    payload = _job_payload(job)
    idx = payload.get("index")
    if idx is None:
        raise RuntimeError("Missing index for analyze")
    idx = int(idx)
    seg_n = f"{idx + 1:03d}"

    project = session.get(Project, job.project_id)
    if not project:
        raise RuntimeError("Project not found")

    seg = session.exec(
        select(Segment).where(Segment.project_id == project.id, Segment.index == idx)
    ).first()
    if seg is None or not seg.video_path:
        raise RuntimeError("Segment or video not found")
    if not Path(seg.video_path).exists():
        raise RuntimeError("Uploaded video missing on disk")

    seg.status = "analyzing"
    seg.updated_at = now_utc()
    session.add(seg)
    session.commit()
    session.refresh(seg)

    _set_job(
        session,
        job,
        progress=15,
        message="Extracting last frame",
        result=_ui_message("jobmsg.analyze.extracting_frame", {"n": seg_n}),
    )
    frame_out = frame_path_for_segment(project.id, idx, ext=".jpg")
    try:
        frame_out.unlink()
    except FileNotFoundError:
        pass
    last_frame = extract_last_frame(seg.video_path, frame_out)
    seg.last_frame_path = str(last_frame)
    session.add(seg)
    session.commit()
    session.refresh(seg)

    start, end = time_range(project, idx)
    _set_job(
        session,
        job,
        progress=55,
        message="Calling multimodal LLM",
        result=_ui_message("jobmsg.analyze.calling_llm", {"n": seg_n}),
    )
    client = DoubaoClient()
    prompts = get_analyzer_prompts(payload.get("locale"))
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

    seg.video_description = description
    seg.status = "completed"
    seg.updated_at = now_utc()
    session.add(seg)

    summary = format_canon_summary(idx, start, end, description)
    project.canon_summaries = append_canon(project.canon_summaries or "", summary)
    project.last_frame_path = seg.last_frame_path
    project.current_segment_index = idx + 1
    project.final_video_path = None
    project.updated_at = now_utc()
    session.add(project)

    session.commit()
    return {"index": idx}


def _run_assemble_job(session: Session, job: Job) -> dict:
    project = session.get(Project, job.project_id)
    if not project:
        raise RuntimeError("Project not found")

    expected = total_segments(project)
    segs = session.exec(select(Segment).where(Segment.project_id == project.id)).all()
    by_index = {s.index: s for s in segs if s.video_path}
    missing = [i for i in range(expected) if i not in by_index]
    if missing:
        raise RuntimeError(f"Missing videos for segments: {missing}")

    video_paths = [by_index[i].video_path for i in range(expected)]  # type: ignore[list-item]
    out = final_video_path_for_project(project.id)

    _set_job(
        session,
        job,
        progress=20,
        message="Running ffmpeg concat",
        result=_ui_message("jobmsg.assemble.running_ffmpeg"),
    )
    final_path = asyncio.run(concatenate_videos(video_paths, out))

    project.final_video_path = str(Path(final_path))
    project.updated_at = now_utc()
    session.add(project)
    session.commit()
    return {"final_video_path": project.final_video_path}


def _run_job(session: Session, job: Job) -> dict:
    if job.type == "full_script":
        return _run_full_script_job(session, job)
    if job.type == "segment_generate":
        return _run_segment_generate_job(session, job)
    if job.type == "extract_frame":
        return _run_extract_frame_job(session, job)
    if job.type == "analyze":
        return _run_analyze_job(session, job)
    if job.type == "assemble":
        return _run_assemble_job(session, job)
    raise RuntimeError(f"Unknown job type: {job.type}")


def _loop() -> None:
    engine = get_engine()
    while not _stop.is_set():
        try:
            with Session(engine) as session:
                job = session.exec(
                    select(Job)
                    .where(Job.status == "queued")
                    .order_by(Job.created_at.asc())
                    .limit(1)
                ).first()

                if not job:
                    time.sleep(0.5)
                    continue

                running_same_project = session.exec(
                    select(Job)
                    .where(Job.project_id == job.project_id, Job.status == "running")
                    .limit(1)
                ).first()
                if running_same_project:
                    time.sleep(0.2)
                    continue

                _set_job(
                    session,
                    job,
                    status="running",
                    progress=1,
                    message="running",
                    error=None,
                    result=_ui_message("jobmsg.running"),
                )

                try:
                    result = _run_job(session, job)
                except Exception as e:
                    _set_job(
                        session,
                        job,
                        status="failed",
                        progress=int(job.progress or 0),
                        message="failed",
                        error=str(e),
                        result=_ui_message("jobmsg.failed"),
                    )
                    continue

                _set_job(
                    session,
                    job,
                    status="succeeded",
                    progress=100,
                    message="succeeded",
                    result={"data": result, **_ui_message("jobmsg.succeeded")},
                )

        except Exception:
            # Avoid worker death; sleep briefly and retry.
            time.sleep(0.5)
