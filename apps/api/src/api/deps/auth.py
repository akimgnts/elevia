"""
auth.py - Authentication dependency for protected routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status

from ..utils import auth_db
from ..utils.auth_security import SESSION_COOKIE_NAME, hash_token


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str
    role: str
    session_id: str


def is_auth_enabled() -> bool:
    return auth_db.has_bootstrapped_users()


def _is_expired(value: str) -> bool:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    return dt <= datetime.now(timezone.utc)


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"message": detail},
    )


def get_optional_user(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Optional[AuthenticatedUser]:
    if not is_auth_enabled():
        return None

    if not session_token:
        return None

    session = auth_db.get_session_by_token_hash(hash_token(session_token))
    if session is None:
        return None
    if session["revoked_at"]:
        return None
    if not bool(session["is_active"]):
        return None
    if _is_expired(str(session["expires_at"])):
        auth_db.revoke_session(str(session["id"]))
        return None

    auth_db.touch_session(str(session["id"]))
    return AuthenticatedUser(
        user_id=str(session["user_id"]),
        email=str(session["email"]),
        role=str(session["role"]),
        session_id=str(session["id"]),
    )


def require_auth(
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> AuthenticatedUser:
    if current_user is None and is_auth_enabled():
        raise _unauthorized()
    if current_user is None:
        raise _unauthorized("Auth not initialized")
    return current_user
