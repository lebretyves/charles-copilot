"""
CHARLES — Authentication JWT.

Gère l'authentification des IADE/MAR via JWT tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger("charles.auth")

# Clé secrète JWT lue depuis env JWT_SECRET (docker-compose / .env)
SECRET_KEY = settings.jwt_secret
TOKEN_EXPIRY = 24 * 3600  # 24h

security = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── Users dev (en production: base de données) ────────────────
# Mot de passe configurable via env CHARLES_DEFAULT_PASSWORD
import os as _os
_DEFAULT_PWD = _os.getenv("CHARLES_DEFAULT_PASSWORD", "charles2026")
_ADMIN_PWD = _os.getenv("CHARLES_ADMIN_PASSWORD", "admin2026")
USERS = {
    "iade1": {"password_hash": _hash_password(_DEFAULT_PWD), "role": "iade", "name": "IADE 1"},
    "iade2": {"password_hash": _hash_password(_DEFAULT_PWD), "role": "iade", "name": "IADE 2"},
    "mar1": {"password_hash": _hash_password(_DEFAULT_PWD), "role": "mar", "name": "MAR 1"},
    "admin": {"password_hash": _hash_password(_ADMIN_PWD), "role": "admin", "name": "Admin"},
}


def _create_token(payload: dict) -> str:
    """Crée un JWT-like token (HMAC-SHA256, pas de dépendance externe)."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload["exp"] = int(time.time()) + TOKEN_EXPIRY
    payload["iat"] = int(time.time())

    import base64
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload, default=str).encode()).rstrip(b"=").decode()
    msg = f"{h}.{p}"
    sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


def _verify_token(token: str) -> dict | None:
    """Vérifie et décode un token."""
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        return None

    msg = f"{parts[0]}.{parts[1]}"
    expected_sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, parts[2]):
        return None

    # Decode payload
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return payload


def verify_token(token: str) -> dict | None:
    """API publique pour vérifier/décoder un token JWT-like."""
    return _verify_token(token)


def authenticate(username: str, password: str) -> dict | None:
    """Authentifie un utilisateur et retourne un token."""
    user = USERS.get(username)
    if not user:
        return None
    if not hmac.compare_digest(user["password_hash"], _hash_password(password)):
        return None
    token = _create_token({"sub": username, "role": user["role"], "name": user["name"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"], "name": user["name"]}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Dépendance FastAPI — extrait l'utilisateur du token. Retourne 401 si absent."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentification requise")

    payload = _verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    return payload


def require_role(*roles: str):
    """Dépendance pour vérifier le rôle."""
    async def check(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Accès interdit")
        return user
    return check
