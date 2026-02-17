#!/usr/bin/env python3

from __future__ import annotations

import argparse

from sqlmodel import Session, select

from autosedance.server.db import get_engine, init_db
from autosedance.server.models import Project, ProjectOwner
from autosedance.server.utils import now_utc


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill ProjectOwner rows for existing projects.")
    p.add_argument("--email", required=True, help="Owner email to assign (for projects missing an owner)")
    args = p.parse_args()

    engine = get_engine()
    init_db(engine)

    email = args.email.strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Invalid --email")

    created = 0
    with Session(engine) as session:
        projects = session.exec(select(Project)).all()
        for proj in projects:
            owner = session.exec(
                select(ProjectOwner).where(ProjectOwner.project_id == proj.id).limit(1)
            ).first()
            if owner:
                continue
            session.add(ProjectOwner(project_id=proj.id, email=email, created_at=now_utc()))
            created += 1
        session.commit()

    print(f"Backfilled {created} projects for {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

