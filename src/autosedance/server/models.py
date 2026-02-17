from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


def _utcnow() -> datetime:
    # Keep it simple (no tz-aware datetime) for SQLite compatibility.
    return datetime.utcnow()


class Project(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    user_prompt: str
    pacing: str = "normal"  # normal | slow | urgent

    total_duration_seconds: int
    segment_duration: int = 15

    full_script: Optional[str] = None
    canon_summaries: str = ""
    current_segment_index: int = 0
    last_frame_path: Optional[str] = None

    final_video_path: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Segment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("project_id", "index"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    index: int = Field(index=True)

    segment_script: str = ""
    video_prompt: str = ""

    video_path: Optional[str] = None
    video_description: Optional[str] = None
    last_frame_path: Optional[str] = None

    # Source of truth should match SegmentRecord.status in autosedance/state/schema.py
    status: str = "pending"

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")

    type: str = Field(index=True)  # full_script|segment_generate|extract_frame|analyze|assemble
    status: str = Field(index=True, default="queued")  # queued|running|succeeded|failed|canceled
    progress: int = 0

    message: str = ""
    error: Optional[str] = None

    payload_json: str = "{}"
    result_json: str = "{}"

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
