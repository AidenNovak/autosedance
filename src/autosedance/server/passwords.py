from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_ALG = "pbkdf2_sha256"
_DEFAULT_ITERS = 200_000
_SALT_BYTES = 16
_DKLEN = 32


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERS) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Stored format: pbkdf2_sha256$<iters>$<salt_b64>$<hash_b64>
    """

    if not isinstance(password, str):
        password = str(password)
    if iterations <= 0:
        iterations = _DEFAULT_ITERS

    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations), dklen=_DKLEN)
    return f"{_ALG}${int(iterations)}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Verify password against a stored hash string."""

    try:
        alg, iters_s, salt_b64, dk_b64 = (stored or "").split("$", 3)
        if alg != _ALG:
            return False
        iters = int(iters_s)
        if iters <= 0:
            return False
        salt = _b64d(salt_b64)
        want = _b64d(dk_b64)
    except Exception:
        return False

    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=len(want))
    return hmac.compare_digest(got, want)

