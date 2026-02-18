from __future__ import annotations

import secrets

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def normalize_invite_code(raw: str) -> str:
    return (raw or "").strip().upper()


def new_invite_code(prefix: str) -> str:
    pref = (prefix or "AS-").strip().upper()
    if pref and not pref.endswith("-"):
        pref = pref + "-"
    body = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(12))
    return f"{pref}{body[:4]}-{body[4:8]}-{body[8:12]}"

