from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import get_settings
from .db import get_engine, init_db
from .routes.full_script import router as full_script_router
from .routes.jobs import router as jobs_router
from .routes.projects import router as projects_router
from .routes.segments import router as segments_router
from .routes.auth import router as auth_router
from .utils import now_utc
from .worker import start_worker

# Ensure SQLModel tables are registered before init_db() runs.
from . import models as _models  # noqa: F401

logger = logging.getLogger(__name__)


class OverloadMiddleware(BaseHTTPMiddleware):
    """Basic in-flight request limiter to avoid overload.

    When the server is saturated, return 503 with a stable error code so the UI
    can show a friendly message + contact info.
    """

    def __init__(self, app: FastAPI, *, max_inflight: int, acquire_timeout_s: float, retry_after_s: int):
        super().__init__(app)
        self._sem = asyncio.Semaphore(max(1, int(max_inflight or 1)))
        self._acquire_timeout_s = max(0.0, float(acquire_timeout_s or 0.0))
        self._retry_after_s = max(1, int(retry_after_s or 10))

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Keep health endpoint responsive for load balancers/ops.
        if request.url.path == "/api/health":
            return await call_next(request)

        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self._acquire_timeout_s)
        except asyncio.TimeoutError:
            logger.warning("OVERLOADED: refusing request %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=503,
                content={"detail": "OVERLOADED"},
                headers={"Retry-After": str(self._retry_after_s)},
            )

        try:
            return await call_next(request)
        finally:
            try:
                self._sem.release()
            except ValueError:
                # Shouldn't happen, but never fail a request on release errors.
                pass


def _seed_invites_if_needed() -> None:
    settings = get_settings()
    if not settings.invite_enabled:
        return

    n = int(settings.invite_seed_count or 0)
    if n <= 0:
        return

    from .invites import new_invite_code
    from .models import InviteCode

    engine = get_engine()
    with Session(engine) as session:
        try:
            existing = session.exec(select(func.count()).select_from(InviteCode)).one()
        except Exception:
            # Table may not exist yet (shouldn't happen after init_db), but never block startup.
            session.rollback()
            return

        cnt = existing[0] if isinstance(existing, tuple) else existing
        if int(cnt or 0) > 0:
            return

        now = now_utc()
        codes: list[str] = []
        seen: set[str] = set()
        for _ in range(n):
            code = new_invite_code(settings.invite_code_prefix)
            while code in seen:
                code = new_invite_code(settings.invite_code_prefix)
            seen.add(code)
            codes.append(code)
            session.add(
                InviteCode(
                    code=code,
                    parent_code=None,
                    owner_user_id=None,
                    redeemed_by_user_id=None,
                    redeemed_at=None,
                    disabled_at=None,
                    created_at=now,
                )
            )

        session.commit()

    # Save seed codes for ops/distribution (best-effort).
    try:
        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "invite_seed_codes.txt"
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for c in codes:
                f.write(c + "\n")
        logger.warning("Seeded %s invite codes (saved to %s)", len(codes), str(path))
    except Exception:
        logger.exception("Failed to write invite seed codes file")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="AutoSedance API", version="0.1.0")

    # CORS for local dev or cross-origin deployments.
    # Security: never combine wildcard origins with credentials.
    if settings.cors_origins.strip():
        origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        allow_origins = origins
        allow_credentials = True
    else:
        allow_origins = ["*"]
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if int(settings.overload_max_inflight_requests) > 0:
        app.add_middleware(
            OverloadMiddleware,
            max_inflight=int(settings.overload_max_inflight_requests),
            acquire_timeout_s=float(settings.overload_acquire_timeout_seconds),
            retry_after_s=int(settings.overload_retry_after_seconds),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server error: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "INTERNAL_ERROR"})

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        _seed_invites_if_needed()
        if not get_settings().disable_worker:
            start_worker()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(full_script_router)
    app.include_router(segments_router)
    app.include_router(jobs_router)

    return app


app = create_app()
