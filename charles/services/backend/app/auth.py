"""
CHARLES - Authentication helpers.

Tokens are HMAC-signed and active users are cached in memory for fast auth.
The cache is bootstrapped from PostgreSQL at startup.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

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

    return hmac.compare_digest(stored_hash, hashlib.sha256(password.encode()).hexdigest())


def normalize_username(username: str) -> str:
    return username.strip().lower()


_DEFAULT_PWD = settings.charles_default_password
_ADMIN_PWD = settings.charles_admin_password


def _build_default_users() -> dict[str, dict[str, Any]]:
    return {
        "iade1": {
            "password_hash": _hash_password(_DEFAULT_PWD),
            "role": "iade",
            "name": "IADE 1",
            "is_active": True,
            "must_change_password": False,
            "source": "builtin",
            "created_by": "bootstrap",
        },
        "iade2": {
            "password_hash": _hash_password(_DEFAULT_PWD),
            "role": "iade",
            "name": "IADE 2",
            "is_active": True,
            "must_change_password": False,
            "source": "builtin",
            "created_by": "bootstrap",
        },
        "mar1": {
            "password_hash": _hash_password(_DEFAULT_PWD),
            "role": "mar",
            "name": "MAR 1",
            "is_active": True,
            "must_change_password": False,
            "source": "builtin",
            "created_by": "bootstrap",
        },
        "admin": {
            "password_hash": _hash_password(_ADMIN_PWD),
            "role": "admin",
            "name": "Admin",
            "is_active": True,
            "must_change_password": False,
            "source": "builtin",
            "created_by": "bootstrap",
        },
    }


USERS: dict[str, dict[str, Any]] = _build_default_users()


def _default_user_rows() -> list[dict[str, Any]]:
    return [{"username": username, **payload} for username, payload in _build_default_users().items()]


def _load_users_into_cache(rows: list[dict[str, Any]]) -> None:
    USERS.clear()
    for row in rows:
        if not row.get("is_active", True):
            continue
        username = normalize_username(str(row["username"]))
        USERS[username] = {
            "password_hash": row["password_hash"],
            "role": row["role"],
            "name": row["name"],
            "is_active": row.get("is_active", True),
            "must_change_password": row.get("must_change_password", False),
            "source": row.get("source", "admin"),
            "created_by": row.get("created_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    if not USERS:
        USERS.update(_build_default_users())


def _get_db_module():
    from app import database as db

    return db


async def refresh_user_store() -> None:
    db = _get_db_module()
    rows = await db.list_user_accounts(include_password_hash=True, include_inactive=False)
    if not rows:
        USERS.clear()
        USERS.update(_build_default_users())
        return
    _load_users_into_cache(rows)


async def bootstrap_user_store() -> None:
    db = _get_db_module()
    for row in _default_user_rows():
        await db.ensure_user_account(row)
    await refresh_user_store()


async def list_users_for_admin() -> list[dict[str, Any]]:
    db = _get_db_module()
    return await db.list_user_accounts(include_password_hash=False, include_inactive=True)


async def create_user_for_admin(
    *,
    username: str,
    password: str,
    role: str,
    name: str,
    created_by: str | None,
    must_change_password: bool = True,
) -> dict[str, Any]:
    db = _get_db_module()
    normalized_username = normalize_username(username)
    if normalized_username in ("", "anonymous"):
        raise ValueError("Nom d'utilisateur invalide")
    if len(password) < 8:
        raise ValueError("Le mot de passe doit contenir au moins 8 caracteres")
    if not name.strip():
        raise ValueError("Le nom affiche est requis")
    if await db.get_user_account(normalized_username):
        raise ValueError("Cet utilisateur existe deja")

    created = await db.create_user_account(
        {
            "username": normalized_username,
            "password_hash": _hash_password(password),
            "role": role,
            "name": name.strip(),
            "is_active": True,
            "must_change_password": must_change_password,
            "source": "admin",
            "created_by": created_by,
        }
    )
    if not created:
        raise ValueError("Creation utilisateur impossible")

    await refresh_user_store()
    return created


def _create_token(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload["exp"] = int(time.time()) + TOKEN_EXPIRY
    payload["iat"] = int(time.time())

    header_text = _b64encode(json.dumps(header).encode())
    payload_text = _b64encode(json.dumps(payload, default=str).encode())
    msg = f"{header_text}.{payload_text}"
    signature = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{signature}"


def _verify_token(token: str) -> dict | None:
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
    return _verify_token(token)


def authenticate(username: str, password: str) -> dict | None:
    normalized_username = normalize_username(username)
    user = USERS.get(normalized_username)
    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    token = _create_token(
        {
            "sub": normalized_username,
            "role": user["role"],
            "name": user["name"],
            "must_change_password": user.get("must_change_password", False),
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "name": user["name"],
        "must_change_password": user.get("must_change_password", False),
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentification requise")

    payload = _verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expire")
    return payload


def require_role(*roles: str):
    async def check(user: dict = Depends(get_current_user)):
        if user.get("sub") in (None, "", "anonymous"):
            raise HTTPException(status_code=401, detail="Authentification requise")
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Acces interdit")
        return user

    return check
