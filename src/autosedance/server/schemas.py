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


class SegmentOut(BaseModel):
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


class ProjectOut(BaseModel):
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
    segments: List[SegmentOut]
