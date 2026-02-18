from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from ..config import get_settings
from .db import get_session
from .models import AuthSession
from .utils import now_utc

logger = logging.getLogger(__name__)

_EPHEMERAL_SECRET: Optional[bytes] = None


def _secret_bytes() -> bytes:
    """Return stable secret bytes for hashing.

    In production you must set AUTH_SECRET_KEY; in dev we fall back to a
    process-local ephemeral secret (sessions/OTPs won't survive restarts).
    """

    settings = get_settings()
    if settings.auth_secret_key:
        return settings.auth_secret_key.encode("utf-8")

    global _EPHEMERAL_SECRET
    if _EPHEMERAL_SECRET is None:
        _EPHEMERAL_SECRET = secrets.token_bytes(32)
        logger.warning("AUTH_SECRET_KEY is empty; using ephemeral secret (dev-only).")
    return _EPHEMERAL_SECRET


def _hmac_sha256_hex(value: str) -> str:
    return hmac.new(_secret_bytes(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_otp(email: str, code: str) -> str:
    return _hmac_sha256_hex(f"otp:{email}:{code}")


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return _hmac_sha256_hex(f"sess:{token}")


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    session_id: str


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[AuthUser]:
    settings = get_settings()
    if not settings.auth_enabled:
        return None

    token = request.cookies.get(settings.session_cookie_name) or ""
    if not token:
        return None

    token_hash = hash_session_token(token)
    rec = session.exec(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
        )
    ).first()
    if not rec:
        return None

    now = now_utc()
    if rec.expires_at and rec.expires_at <= now:
        return None

    # Best-effort last seen tracking (don't fail auth if this write fails).
    try:
        rec.last_seen_at = now
        session.add(rec)
        session.commit()
    except Exception:
        session.rollback()

    return AuthUser(user_id=rec.email, session_id=rec.id)


def require_user(
    user: Optional[AuthUser] = Depends(get_current_user),
) -> AuthUser:
    settings = get_settings()
    if not settings.auth_enabled or not settings.auth_require_for_writes:
        # Auth is disabled or optional; allow the request through.
        return user or AuthUser(user_id="", session_id="")

    if not user:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    return user


def require_read_user(
    user: Optional[AuthUser] = Depends(get_current_user),
) -> AuthUser:
    settings = get_settings()
    if not settings.auth_enabled or not settings.auth_require_for_reads:
        return user or AuthUser(user_id="", session_id="")
    if not user:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    return user
