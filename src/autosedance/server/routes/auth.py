from __future__ import annotations

import logging
import re
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from ...config import get_settings
from ..auth import (
    AuthUser,
    get_current_user,
    hash_otp,
    hash_session_token,
    new_session_token,
)
from ..db import get_session
from ..email import send_otp_email
from ..models import AuthSession, EmailOtp
from ..ratelimit import bump_counter, make_window_key, maybe_cleanup_expired
from ..schemas import AuthMeOut, AuthOkOut, AuthRequestCodeIn, AuthVerifyCodeIn
from ..utils import now_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _validate_email(email: str) -> None:
    if not email or len(email) > 254 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="EMAIL_INVALID")

    settings = get_settings()
    allowlist = [e.strip().lower() for e in (settings.auth_email_allowlist or "").split(",") if e.strip()]
    if allowlist and email not in allowlist:
        raise HTTPException(status_code=403, detail="EMAIL_NOT_ALLOWED")


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    max_age = int(settings.auth_session_ttl_days) * 24 * 3600
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain or None,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.session_cookie_domain or None,
        path="/",
    )


def _client_ip(request: Request) -> str:
    settings = get_settings()
    direct = (request.client.host if request.client else "") or "unknown"
    if not settings.trust_proxy_headers:
        return direct

    trusted = [ip.strip() for ip in (settings.trusted_proxy_ips or "").split(",") if ip.strip()]
    if trusted and direct not in trusted:
        return direct

    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri:
        return xri
    return direct


@router.post("/request_code", response_model=AuthOkOut)
def request_code(
    request: Request,
    payload: AuthRequestCodeIn,
    session: Session = Depends(get_session),
) -> AuthOkOut:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="AUTH_DISABLED")

    email = _normalize_email(payload.email)
    _validate_email(email)

    now = now_utc()
    maybe_cleanup_expired(session, now=now)

    ip = _client_ip(request)
    if int(settings.auth_rl_request_code_per_ip_per_hour) > 0:
        key = make_window_key("auth:reqcode:ip", ip, now=now, window_seconds=3600)
        n = bump_counter(session, key=key, now=now)
        if n > int(settings.auth_rl_request_code_per_ip_per_hour):
            raise HTTPException(status_code=429, detail="RL_LIMITED")

    if int(settings.auth_rl_request_code_per_email_per_hour) > 0:
        key = make_window_key("auth:reqcode:email", email, now=now, window_seconds=3600)
        n = bump_counter(session, key=key, now=now)
        if n > int(settings.auth_rl_request_code_per_email_per_hour):
            raise HTTPException(status_code=429, detail="RL_LIMITED")

    latest = session.exec(
        select(EmailOtp).where(EmailOtp.email == email).order_by(EmailOtp.created_at.desc()).limit(1)
    ).first()
    if latest and (now - latest.created_at).total_seconds() < int(settings.auth_otp_min_interval_seconds):
        raise HTTPException(status_code=429, detail="OTP_TOO_FREQUENT")

    code = f"{secrets.randbelow(1_000_000):06d}"
    rec = EmailOtp(
        email=email,
        code_hash=hash_otp(email, code),
        attempts=0,
        consumed_at=None,
        expires_at=now + timedelta(minutes=int(settings.auth_otp_ttl_minutes)),
        created_at=now,
        updated_at=now,
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    try:
        send_otp_email(email, code, ttl_minutes=int(settings.auth_otp_ttl_minutes))
    except Exception:
        # Don't leave a valid OTP around if we failed to deliver it.
        try:
            session.delete(rec)
            session.commit()
        except Exception:
            session.rollback()
        logger.exception("Failed to send OTP email")
        raise HTTPException(status_code=500, detail="OTP_SEND_FAILED")

    return AuthOkOut(ok=True)


@router.post("/verify_code", response_model=AuthMeOut)
def verify_code(
    request: Request,
    payload: AuthVerifyCodeIn,
    response: Response,
    session: Session = Depends(get_session),
) -> AuthMeOut:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="AUTH_DISABLED")

    email = _normalize_email(payload.email)
    _validate_email(email)

    code = (payload.code or "").strip()
    if not (len(code) == 6 and code.isdigit()):
        raise HTTPException(status_code=400, detail="CODE_INVALID")

    now = now_utc()
    maybe_cleanup_expired(session, now=now)
    ip = _client_ip(request)
    if int(settings.auth_rl_verify_per_ip_per_hour) > 0:
        key = make_window_key("auth:verify:ip", ip, now=now, window_seconds=3600)
        n = bump_counter(session, key=key, now=now)
        if n > int(settings.auth_rl_verify_per_ip_per_hour):
            raise HTTPException(status_code=429, detail="RL_LIMITED")

    stmt = (
        select(EmailOtp)
        .where(
            EmailOtp.email == email,
            EmailOtp.consumed_at.is_(None),
            EmailOtp.expires_at > now,
        )
        .order_by(EmailOtp.created_at.desc())
    )
    candidates = session.exec(stmt).all()
    if not candidates:
        raise HTTPException(status_code=400, detail="CODE_EXPIRED")

    want = hash_otp(email, code)
    matched: Optional[EmailOtp] = None
    for c in candidates:
        if c.code_hash == want:
            matched = c
            break

    if not matched:
        # Increment attempts on the newest code to slow brute-force.
        newest = candidates[0]
        newest.attempts = int(newest.attempts or 0) + 1
        newest.updated_at = now
        if newest.attempts >= int(settings.auth_otp_max_verify_attempts):
            newest.consumed_at = now
        session.add(newest)
        session.commit()
        raise HTTPException(status_code=400, detail="CODE_INVALID")

    matched.consumed_at = now
    matched.updated_at = now
    session.add(matched)
    session.commit()

    token = new_session_token()
    sess = AuthSession(
        email=email,
        token_hash=hash_session_token(token),
        created_at=now,
        expires_at=now + timedelta(days=int(settings.auth_session_ttl_days)),
        revoked_at=None,
        last_seen_at=now,
    )
    session.add(sess)
    session.commit()
    session.refresh(sess)

    _set_session_cookie(response, token)
    return AuthMeOut(authenticated=True, email=email)


@router.get("/me", response_model=AuthMeOut)
def me(user: Optional[AuthUser] = Depends(get_current_user)) -> AuthMeOut:
    if not user:
        return AuthMeOut(authenticated=False, email=None)
    return AuthMeOut(authenticated=True, email=user.email)


@router.post("/logout", response_model=AuthOkOut)
def logout(
    request: Request,
    response: Response,
    user: Optional[AuthUser] = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AuthOkOut:
    if user:
        rec = session.get(AuthSession, user.session_id)
        if rec and rec.revoked_at is None:
            rec.revoked_at = now_utc()
            session.add(rec)
            session.commit()

    _clear_session_cookie(response)
    return AuthOkOut(ok=True)
