import base64
import hashlib
import hmac
import json
import os
import time
from collections import deque
from typing import Callable

SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
MIN_PASSWORD_LENGTH = 10
HEADER = {"alg": "HS256", "typ": "JWT"}


class AuthError(Exception):
    pass


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
        return hmac.compare_digest(_b64(digest), expected)
    except (ValueError, TypeError):
        return False


def _sign(secret: str, signing_input: str) -> str:
    return _b64(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())


def issue_token(secret: str, claims: dict, ttl_seconds: int, now: float | None = None) -> str:
    if not secret:
        raise AuthError("signing secret is not configured")
    issued = int(now if now is not None else time.time())
    body = {**claims, "iat": issued, "exp": issued + ttl_seconds}
    signing_input = _b64(json.dumps(HEADER, separators=(",", ":")).encode()) + "." + _b64(json.dumps(body, separators=(",", ":")).encode())
    return signing_input + "." + _sign(secret, signing_input)


def verify_token(secret: str, token: str, expected_type: str, now: float | None = None) -> dict:
    if not secret:
        raise AuthError("signing secret is not configured")
    try:
        header_part, body_part, signature = token.split(".")
        header = json.loads(_unb64(header_part))
        claims = json.loads(_unb64(body_part))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise AuthError("malformed token")
    if header != HEADER:
        raise AuthError("unsupported token header")
    if not hmac.compare_digest(_sign(secret, header_part + "." + body_part), signature):
        raise AuthError("bad signature")
    if claims.get("typ") != expected_type:
        raise AuthError("wrong token type")
    if claims.get("exp", 0) <= (now if now is not None else time.time()):
        raise AuthError("token expired")
    return claims


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True
