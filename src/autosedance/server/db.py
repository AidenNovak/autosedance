from __future__ import annotations

from pathlib import Path
from typing import Generator, Optional

from sqlmodel import SQLModel, Session, create_engine

from ..config import get_settings

_engine = None
_engine_url = None


def _default_sqlite_url() -> str:
    settings = get_settings()
    out_dir = Path(settings.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "autosedance.sqlite3"
    return f"sqlite:///{db_path}"


def get_engine():
    global _engine, _engine_url
    settings = get_settings()
    url = settings.database_url or _default_sqlite_url()

    if _engine is None or _engine_url != url:
        _engine_url = url
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
    return _engine


def reset_engine_for_tests() -> None:
    global _engine, _engine_url
    _engine = None
    _engine_url = None


def init_db(engine=None) -> None:
    if engine is None:
        engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    engine = get_engine()
    with Session(engine) as session:
        yield session

