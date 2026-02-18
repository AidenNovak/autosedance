from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from .models import ProjectOwner


def require_project_owner(session: Session, project_id: str, user_id: str) -> None:
    """Ensure the project belongs to the given user_id.

    Use 404 to avoid leaking project existence.
    When user_id is empty (auth disabled), this becomes a no-op.
    """

    if not user_id:
        return
    rec = session.exec(
        select(ProjectOwner).where(ProjectOwner.project_id == project_id, ProjectOwner.email == user_id).limit(1)
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Project not found")
