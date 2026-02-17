from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from .models import ProjectOwner


def require_project_owner(session: Session, project_id: str, email: str) -> None:
    """Ensure the project belongs to the given email.

    Use 404 to avoid leaking project existence.
    When email is empty (auth disabled), this becomes a no-op.
    """

    if not email:
        return
    rec = session.exec(
        select(ProjectOwner).where(ProjectOwner.project_id == project_id, ProjectOwner.email == email).limit(1)
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Project not found")

