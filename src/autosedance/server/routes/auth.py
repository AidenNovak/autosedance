from __future__ import annotations

import logging
import re
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import update as sa_update
from sqlmodel import Session, select

from ...config import get_settings
from ..auth import AuthUser, get_current_user, hash_session_token, new_session_token
from ..db import get_session
from ..invites import new_invite_code, normalize_invite_code
from ..models import AuthSession, InviteCode, UserAccount, UserLead
from ..passwords import hash_password, verify_password
from ..ratelimit import bump_counter, make_window_key, maybe_cleanup_expired
from ..schemas import AuthInvitesOut, AuthLoginIn, AuthMeOut, AuthOkOut, AuthRegisterIn, AuthRegisterOut
from ..utils import now_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Note: use a raw string with single escapes; r"\\s" would match a literal backslash + "s".
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,24}$")

_ALLOWED_REFERRALS = {
    "x",
    "reddit",
    "youtube",
    "tiktok",
    "discord",
    "github",
    "product_hunt",
    "friend",
    "other",
}

_MAX_COUNTRY_LEN = 64
_MAX_REFERRAL_LEN = 32
_MAX_OPINION_LEN = 2000
_MAX_UA_LEN = 300

_MIN_PASSWORD_LEN = 10
_MAX_PASSWORD_LEN = 200


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _normalize_username(raw: str) -> str:
    return (raw or "").strip().lower()


def _validate_email(email: str) -> None:
    if not email or len(email) > 254 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="EMAIL_INVALID")

    settings = get_settings()
    allowlist = [e.strip().lower() for e in (settings.auth_email_allowlist or "").split(",") if e.strip()]
    if allowlist and email not in allowlist:
        raise HTTPException(status_code=403, detail="EMAIL_NOT_ALLOWED")


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="USERNAME_INVALID")


def _validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise HTTPException(status_code=400, detail="PASSWORD_INVALID")
    if len(password) < _MIN_PASSWORD_LEN:
        raise HTTPException(status_code=400, detail="PASSWORD_TOO_WEAK")
    if len(password) > _MAX_PASSWORD_LEN:
        raise HTTPException(status_code=400, detail="PASSWORD_TOO_LONG")


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


def _sanitize_username_base(raw: str) -> str:
    s = (raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "user"
    if len(s) < 3:
        s = f"user_{s}"
    # Leave room for suffix when we need to resolve collisions.
    if len(s) > 18:
        s = s[:18].rstrip("_") or "user"
    return s


def _find_available_username(session: Session, desired: str, *, base_fallback: str) -> str:
    desired = _normalize_username(desired)
    if desired:
        _validate_username(desired)
        existing = session.exec(select(UserAccount).where(UserAccount.username == desired).limit(1)).first()
        if existing:
            raise HTTPException(status_code=409, detail="USERNAME_TAKEN")
        return desired

    base = _sanitize_username_base(base_fallback)
    for i in range(30):
        if i == 0:
            candidate = base
        else:
            candidate = f"{base}_{secrets.token_hex(2)}"  # 4 hex chars
        candidate = candidate[:24]
        if not _USERNAME_RE.match(candidate):
            continue
        existing = session.exec(select(UserAccount).where(UserAccount.username == candidate).limit(1)).first()
        if not existing:
            return candidate
    raise HTTPException(status_code=409, detail="USERNAME_TAKEN")


@router.post("/register", response_model=AuthRegisterOut)
def register(
    request: Request,
    payload: AuthRegisterIn,
    response: Response,
    session: Session = Depends(get_session),
) -> AuthRegisterOut:
    """Invite-gated registration.

    Redeems one invite code and mints 5 child invites for the new user.
    """

    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="AUTH_DISABLED")

    if settings.invite_enabled and not (payload.invite_code or "").strip():
        raise HTTPException(status_code=400, detail="INVITE_REQUIRED")

    email = _normalize_email(payload.email)
    _validate_email(email)

    username = _find_available_username(
        session,
        desired=(payload.username or ""),
        base_fallback=email.split("@")[0] if "@" in email else "user",
    )

    _validate_password(payload.password)

    country = (payload.country or "").strip()
    if not country or len(country) > _MAX_COUNTRY_LEN:
        raise HTTPException(status_code=400, detail="COUNTRY_INVALID")

    referral = (payload.referral or "").strip()
    if not referral or len(referral) > _MAX_REFERRAL_LEN or referral not in _ALLOWED_REFERRALS:
        raise HTTPException(status_code=400, detail="REFERRAL_INVALID")

    opinion = (payload.opinion or "").strip()
    if len(opinion) > _MAX_OPINION_LEN:
        raise HTTPException(status_code=400, detail="OPINION_TOO_LONG")

    now = now_utc()
    maybe_cleanup_expired(session, now=now)

    ip = _client_ip(request)
    if int(settings.auth_rl_register_per_ip_per_hour) > 0:
        key = make_window_key("auth:register:ip", ip, now=now, window_seconds=3600)
        n = bump_counter(session, key=key, now=now)
        if n > int(settings.auth_rl_register_per_ip_per_hour):
            raise HTTPException(status_code=429, detail="RL_LIMITED")

    if int(settings.auth_rl_register_per_email_per_hour) > 0:
        key = make_window_key("auth:register:email", email, now=now, window_seconds=3600)
        n = bump_counter(session, key=key, now=now)
        if n > int(settings.auth_rl_register_per_email_per_hour):
            raise HTTPException(status_code=429, detail="RL_LIMITED")

    ua = (request.headers.get("user-agent") or "").strip()
    if ua and len(ua) > _MAX_UA_LEN:
        ua = ua[:_MAX_UA_LEN]

    lead = session.exec(select(UserLead).where(UserLead.email == email).limit(1)).first()
    if lead is None:
        lead = UserLead(
            email=email,
            country=country,
            referral=referral,
            opinion=opinion,
            ip=ip,
            user_agent=ua or None,
            created_at=now,
            updated_at=now,
        )
    else:
        lead.country = country
        lead.referral = referral
        lead.opinion = opinion
        lead.ip = ip
        lead.user_agent = ua or None
        lead.updated_at = now

    invite_code = normalize_invite_code(payload.invite_code)
    if settings.invite_enabled:
        rec = session.get(InviteCode, invite_code)
        if not rec:
            raise HTTPException(status_code=400, detail="INVITE_INVALID")
        if rec.disabled_at is not None:
            raise HTTPException(status_code=400, detail="INVITE_DISABLED")

    user = UserAccount(
        username=username,
        password_hash=hash_password(payload.password),
        email=email,
        created_at=now,
        updated_at=now,
    )

    # Create a session token that references the user_id as the principal.
    token = new_session_token()
    sess = AuthSession(
        email=user.id,
        token_hash=hash_session_token(token),
        created_at=now,
        expires_at=now + timedelta(days=int(settings.auth_session_ttl_days)),
        revoked_at=None,
        last_seen_at=now,
    )

    session.add(lead)
    session.add(user)

    # Redeem invite atomically (single-use).
    if settings.invite_enabled:
        stmt = (
            sa_update(InviteCode)
            .where(
                InviteCode.code == invite_code,
                InviteCode.redeemed_at.is_(None),
                InviteCode.disabled_at.is_(None),
            )
            .values(redeemed_by_user_id=user.id, redeemed_at=now)
        )
        res = session.exec(stmt)
        if not getattr(res, "rowcount", 0):
            raise HTTPException(status_code=400, detail="INVITE_USED")

    # Mint child invites for the new user.
    children = []
    if settings.invite_enabled:
        n_children = int(settings.invite_children_per_redeem or 0)
        if n_children < 0:
            n_children = 0
        for _ in range(n_children):
            for _attempt in range(50):
                code = new_invite_code(settings.invite_code_prefix)
                if session.get(InviteCode, code) is not None:
                    continue
                session.add(
                    InviteCode(
                        code=code,
                        parent_code=invite_code,
                        owner_user_id=user.id,
                        redeemed_by_user_id=None,
                        redeemed_at=None,
                        disabled_at=None,
                        created_at=now,
                    )
                )
                children.append(code)
                break
            else:
                raise HTTPException(status_code=500, detail="INVITE_GENERATE_FAILED")

    session.add(sess)
    session.commit()
    session.refresh(user)
    session.refresh(sess)

    _set_session_cookie(response, token)
    return AuthRegisterOut(
        authenticated=True,
        user_id=user.id,
        username=user.username,
        email=user.email,
        invites=children,
    )


@router.post("/login", response_model=AuthMeOut)
def login(
    request: Request,
    payload: AuthLoginIn,
    response: Response,
    session: Session = Depends(get_session),
) -> AuthMeOut:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="AUTH_DISABLED")

    now = now_utc()
    maybe_cleanup_expired(session, now=now)

    ip = _client_ip(request)
    if int(settings.auth_rl_login_per_ip_per_hour) > 0:
        key = make_window_key("auth:login:ip", ip, now=now, window_seconds=3600)
        n = bump_counter(session, key=key, now=now)
        if n > int(settings.auth_rl_login_per_ip_per_hour):
            raise HTTPException(status_code=429, detail="RL_LIMITED")

    username = _normalize_username(payload.username)
    _validate_username(username)
    password = payload.password or ""

    user = session.exec(select(UserAccount).where(UserAccount.username == username).limit(1)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="LOGIN_FAILED")

    token = new_session_token()
    sess = AuthSession(
        email=user.id,
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
    return AuthMeOut(authenticated=True, user_id=user.id, username=user.username, email=user.email)


@router.get("/invites", response_model=AuthInvitesOut)
def my_invites(
    user: Optional[AuthUser] = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AuthInvitesOut:
    if not user:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")

    recs = session.exec(
        select(InviteCode)
        .where(
            InviteCode.owner_user_id == user.user_id,
            InviteCode.redeemed_at.is_(None),
            InviteCode.disabled_at.is_(None),
        )
        .order_by(InviteCode.created_at.desc())
    ).all()
    return AuthInvitesOut(invites=[r.code for r in recs])


@router.get("/me", response_model=AuthMeOut)
def me(
    user: Optional[AuthUser] = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AuthMeOut:
    if not user:
        return AuthMeOut(authenticated=False, user_id=None, username=None, email=None)

    acc = session.get(UserAccount, user.user_id)
    if not acc:
        return AuthMeOut(authenticated=False, user_id=None, username=None, email=None)

    return AuthMeOut(authenticated=True, user_id=acc.id, username=acc.username, email=acc.email)


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
