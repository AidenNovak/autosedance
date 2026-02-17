from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from .db import init_db
from .routes.full_script import router as full_script_router
from .routes.jobs import router as jobs_router
from .routes.projects import router as projects_router
from .routes.segments import router as segments_router
from .worker import start_worker

# Ensure SQLModel tables are registered before init_db() runs.
from . import models as _models  # noqa: F401


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="AutoSedance API", version="0.1.0")

    # CORS for local dev (Next.js on :3000 talking to backend on :8000)
    if settings.cors_origins.strip():
        origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        allow_origins = origins
    else:
        allow_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        if not get_settings().disable_worker:
            start_worker()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(projects_router)
    app.include_router(full_script_router)
    app.include_router(segments_router)
    app.include_router(jobs_router)

    return app


app = create_app()
