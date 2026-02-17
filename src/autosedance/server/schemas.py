from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Pacing = Literal["normal", "slow", "urgent"]
SegmentStatus = Literal[
    "pending",
    "script_ready",
    "waiting_video",
    "analyzing",
    "completed",
    "failed",
]

JobType = Literal["full_script", "segment_generate", "extract_frame", "analyze", "assemble"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]


class CreateProjectIn(BaseModel):
    user_prompt: str
    total_duration_seconds: int = Field(ge=1)
    segment_duration: int = Field(default=15, ge=1)
    pacing: Pacing = "normal"


class UpdateFullScriptIn(BaseModel):
    full_script: str
    invalidate_downstream: bool = True


class GenerateWithFeedbackIn(BaseModel):
    feedback: Optional[str] = None


class UpdateSegmentIn(BaseModel):
    segment_script: Optional[str] = None
    video_prompt: Optional[str] = None
    invalidate_downstream: bool = True


class SegmentSummaryOut(BaseModel):
    index: int
    status: str
    has_video: bool
    has_frame: bool
    has_description: bool
    updated_at: datetime
    video_url: Optional[str] = None
    frame_url: Optional[str] = None


class SegmentDetailOut(BaseModel):
    index: int
    segment_script: str = ""
    video_prompt: str = ""
    status: str
    video_description: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)

    # Debug/ops fields (UI should prefer the /video and /frame endpoints)
    video_path: Optional[str] = None
    last_frame_path: Optional[str] = None

    # Convenience URLs for the frontend
    video_url: Optional[str] = None
    frame_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProjectSummaryOut(BaseModel):
    id: str
    user_prompt: str
    pacing: str
    total_duration_seconds: int
    segment_duration: int
    current_segment_index: int = 0

    created_at: datetime
    updated_at: datetime

    num_segments: int
    next_action: str

    segments_completed: int = 0
    segments_with_video: int = 0
    segments_with_frame: int = 0
    segments_with_description: int = 0


class ProjectDetailOut(BaseModel):
    id: str
    user_prompt: str
    pacing: str
    total_duration_seconds: int
    segment_duration: int

    full_script: Optional[str] = None
    canon_summaries: str = ""
    current_segment_index: int = 0
    last_frame_path: Optional[str] = None
    final_video_path: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    num_segments: int
    next_action: str
    segments: List[SegmentSummaryOut]


class CreateJobIn(BaseModel):
    type: JobType
    index: Optional[int] = None
    feedback: Optional[str] = None
    locale: Optional[str] = None


class JobOut(BaseModel):
    id: str
    project_id: str
    type: JobType
    status: JobStatus
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AuthRequestCodeIn(BaseModel):
    email: str


class AuthVerifyCodeIn(BaseModel):
    email: str
    code: str


class AuthMeOut(BaseModel):
    authenticated: bool
    email: Optional[str] = None


class AuthOkOut(BaseModel):
    ok: bool = True


# Backwards-compatible aliases (legacy endpoints/tests may still import these).
SegmentOut = SegmentDetailOut
ProjectOut = ProjectDetailOut
