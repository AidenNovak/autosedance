from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from ..config import get_settings


def get_projects_root() -> Path:
    settings = get_settings()
    if settings.projects_dir:
        root = Path(settings.projects_dir)
    else:
        root = Path(settings.output_dir) / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_dir(project_id: str) -> Path:
    return get_projects_root() / project_id


def ensure_project_dirs(project_id: str) -> Path:
    root = project_dir(project_id)
    (root / "segments").mkdir(parents=True, exist_ok=True)
    (root / "input_videos").mkdir(parents=True, exist_ok=True)
    (root / "frames").mkdir(parents=True, exist_ok=True)
    (root / "final").mkdir(parents=True, exist_ok=True)
    return root


def full_script_path(project_id: str) -> Path:
    return ensure_project_dirs(project_id) / "full_script.txt"


def segment_txt_path(project_id: str, index: int) -> Path:
    return ensure_project_dirs(project_id) / "segments" / f"segment_{index:03d}.txt"


def input_video_path(project_id: str, index: int, original_filename: Optional[str] = None) -> Path:
    root = ensure_project_dirs(project_id) / "input_videos"
    suffix = ".mp4"
    if original_filename:
        _, ext = os.path.splitext(original_filename)
        if ext:
            suffix = ext.lower()
    return root / f"segment_{index:03d}{suffix}"


def frame_path(project_id: str, index: int, ext: str = ".jpg") -> Path:
    return ensure_project_dirs(project_id) / "frames" / f"frame_{index:03d}{ext}"


def final_video_path(project_id: str) -> Path:
    return ensure_project_dirs(project_id) / "final" / "output.mp4"


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

