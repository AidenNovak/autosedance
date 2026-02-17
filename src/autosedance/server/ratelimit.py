from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import delete
from sqlmodel import Session

from .models import RateLimitCounter

_last_cleanup_at: Optional[datetime] = None


@dataclass(frozen=True)
class RateLimitKey:
    key: str
    expires_at: datetime


def make_window_key(namespace: str, subject: str, *, now: datetime, window_seconds: int) -> RateLimitKey:
    if window_seconds <= 0:
        window_seconds = 3600
    # now_utc() returns a naive UTC datetime; avoid datetime.timestamp() because
    # it treats naive datetimes as local time.
    epoch = int((now - datetime(1970, 1, 1)).total_seconds())
    bucket = epoch // int(window_seconds)
    start_ts = bucket * int(window_seconds)
    expires = datetime.utcfromtimestamp(start_ts + int(window_seconds))
    return RateLimitKey(key=f"{namespace}:{subject}:{bucket}", expires_at=expires)


def maybe_cleanup_expired(session: Session, *, now: datetime, interval_seconds: int = 600) -> None:
    """Best-effort cleanup of expired counters (throttled per process)."""

    global _last_cleanup_at
    if _last_cleanup_at is not None and (now - _last_cleanup_at).total_seconds() < interval_seconds:
        return
    _last_cleanup_at = now
    try:
        session.exec(delete(RateLimitCounter).where(RateLimitCounter.expires_at <= now))
        session.commit()
    except Exception:
        session.rollback()


def bump_counter(session: Session, *, key: RateLimitKey, now: datetime) -> int:
    """Increment the counter for a key and return the new count."""

    rec = session.get(RateLimitCounter, key.key)
    if rec is None:
        rec = RateLimitCounter(
            key=key.key,
            count=1,
            expires_at=key.expires_at,
            created_at=now,
            updated_at=now,
        )
    elif rec.expires_at <= now:
        # Reset within the same primary key to avoid UNIQUE constraint conflicts.
        rec.count = 1
        rec.expires_at = key.expires_at
        rec.updated_at = now
    else:
        rec.count = int(rec.count or 0) + 1
        rec.updated_at = now
    session.add(rec)

    try:
        session.commit()
        session.refresh(rec)
        return int(rec.count or 0)
    except Exception:
        # Handle rare race on insert/update by retrying once.
        session.rollback()
        rec2 = session.get(RateLimitCounter, key.key)
        if rec2 is None:
            rec2 = RateLimitCounter(
                key=key.key,
                count=1,
                expires_at=key.expires_at,
                created_at=now,
                updated_at=now,
            )
        elif rec2.expires_at <= now:
            rec2.count = 1
            rec2.expires_at = key.expires_at
            rec2.updated_at = now
        else:
            rec2.count = int(rec2.count or 0) + 1
            rec2.updated_at = now
        session.add(rec2)
        session.commit()
        session.refresh(rec2)
        return int(rec2.count or 0)
