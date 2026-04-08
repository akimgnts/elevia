"""
auth.py - MVP login/logout/me endpoints.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..deps.auth import AuthenticatedUser, get_optional_user, require_auth, is_auth_enabled
from ..schemas.auth import (
    AuthUser,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SaveProfileRequest,
    StoredProfileResponse,
)
from ..utils import auth_db
from ..utils.auth_security import (
    SESSION_COOKIE_NAME,
    generate_session_token,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_auth_user(user_id: str, email: str, role: str) -> AuthUser:
    return AuthUser(id=user_id, email=email, role=role)


def _set_session_cookie(response: Response, session_token: str, expires_at: str) -> None:
    expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        expires=expires,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response) -> LoginResponse:
    if not is_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Auth not initialized. Create the admin user first."},
        )

    user = auth_db.get_user_by_email(payload.email)
    if user is None or not bool(user["is_active"]) or not verify_password(payload.password, str(user["password_hash"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid credentials"},
        )

    raw_token = generate_session_token()
    session = auth_db.create_session(str(user["id"]), hash_token(raw_token))
    _set_session_cookie(response, raw_token, str(session["expires_at"]))
    return LoginResponse(
        expires_at=str(session["expires_at"]),
        user=_to_auth_user(str(user["id"]), str(user["email"]), str(user["role"])),
    )


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: AuthenticatedUser | None = Depends(get_optional_user),
) -> MeResponse:
    if current_user is None:
        return MeResponse(authenticated=False, auth_enabled=is_auth_enabled(), user=None)

    return MeResponse(
        authenticated=True,
        auth_enabled=True,
        user=_to_auth_user(current_user.user_id, current_user.email, current_user.role),
    )


@router.post("/logout", status_code=204)
async def logout(response: Response, current_user: AuthenticatedUser | None = Depends(get_optional_user)) -> None:
    if current_user is not None:
        auth_db.revoke_session(current_user.session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return None


@router.get("/profile", response_model=StoredProfileResponse)
async def get_profile(current_user: AuthenticatedUser = Depends(require_auth)) -> StoredProfileResponse:
    payload = auth_db.get_profile(current_user.user_id)
    if payload is None:
        return StoredProfileResponse(profile=None, updated_at=None)
    return StoredProfileResponse(**payload)


@router.put("/profile", response_model=StoredProfileResponse)
async def save_profile(
    payload: SaveProfileRequest,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> StoredProfileResponse:
    stored = auth_db.upsert_profile(current_user.user_id, payload.profile)
    return StoredProfileResponse(**stored)
