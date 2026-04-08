"""
auth.py - Schemas for MVP authentication.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)


class AuthUser(BaseModel):
    id: str
    email: str
    role: str


class LoginResponse(BaseModel):
    expires_at: str
    user: AuthUser


class MeResponse(BaseModel):
    authenticated: bool
    auth_enabled: bool
    user: Optional[AuthUser] = None


class StoredProfileResponse(BaseModel):
    profile: Optional[dict] = None
    updated_at: Optional[str] = None


class SaveProfileRequest(BaseModel):
    profile: dict
