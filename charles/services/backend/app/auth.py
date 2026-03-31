"""
CHARLES - Authentication helpers.

JWT-like token handling plus a small in-memory user store for local/dev usage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger("charles.auth")

SECRET_KEY = settings.jwt_secret
TOKEN_EXPIRY = settings.auth_token_expiry_hours * 3600
PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000

security = HTTPBearer(auto_error=False)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith(f"{PBKDF2_PREFIX}$"):
        try:
            _, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
            iterations = int(iterations_text)
        except ValueError:
            return False

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            _b64decode(salt_text),
            iterations,
        )
        return hmac.compare_digest(candidate, _b64decode(digest_text))

    # Legacy SHA-256 compatibility for older hashes.
    return hmac.compare_digest(stored_hash, hashlib.sha256(password.encode()).hexdigest())


_DEFAULT_PWD = settings.charles_default_password
_ADMIN_PWD = settings.charles_admin_password
USERS = {
    "iade1": {"password_hash": _hash_password(_DEFAULT_PWD), "role": "iade", "name": "IADE 1"},
    "iade2": {"password_hash": _hash_password(_DEFAULT_PWD), "role": "iade", "name": "IADE 2"},
    "mar1": {"password_hash": _hash_password(_DEFAULT_PWD), "role": "mar", "name": "MAR 1"},
    "admin": {"password_hash": _hash_password(_ADMIN_PWD), "role": "admin", "name": "Admin"},
}


def _create_token(payload: dict) -> str:
    """Create a JWT-like token (HMAC-SHA256, no external dependency)."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload["exp"] = int(time.time()) + TOKEN_EXPIRY
    payload["iat"] = int(time.time())

    header_text = _b64encode(json.dumps(header).encode())
    payload_text = _b64encode(json.dumps(payload, default=str).encode())
    msg = f"{header_text}.{payload_text}"
    signature = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{signature}"


def _verify_token(token: str) -> dict | None:
    """Verify and decode a token."""
    parts = token.split(".")
    if len(parts) != 3:
        return None

    msg = f"{parts[0]}.{parts[1]}"
    expected_sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, parts[2]):
        return None

    try:
        payload = json.loads(_b64decode(parts[1]))
    except Exception:
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return payload


def verify_token(token: str) -> dict | None:
    """Public API used by REST and WebSocket auth."""
    return _verify_token(token)


def authenticate(username: str, password: str) -> dict | None:
    """Authenticate a user and return a bearer token."""
    user = USERS.get(username)
    if not user:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    token = _create_token({"sub": username, "role": user["role"], "name": user["name"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"], "name": user["name"]}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """FastAPI dependency that extracts the current user from the bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentification requise")

    payload = _verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expire")
    return payload


def require_role(*roles: str):
    """FastAPI dependency that enforces an allowed role list."""

    async def check(user: dict = Depends(get_current_user)):
        if user.get("sub") in (None, "", "anonymous"):
            raise HTTPException(status_code=401, detail="Authentification requise")
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Acces interdit")
        return user

    return check
