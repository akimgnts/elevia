"""
inbox.py - Pydantic schemas for Inbox endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InboxRequest(BaseModel):
    profile_id: str
    profile: Dict[str, Any]
    min_score: int = Field(default=65, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)


class InboxItem(BaseModel):
    offer_id: str
    title: str
    company: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    score: int = Field(..., ge=0, le=100)
    reasons: List[str] = Field(default_factory=list)


class InboxResponse(BaseModel):
    profile_id: str
    items: List[InboxItem]
    total_matched: int
    total_decided: int


class DecisionRequest(BaseModel):
    profile_id: str
    status: str = Field(..., pattern="^(SHORTLISTED|DISMISSED)$")
    note: Optional[str] = None


class DecisionResponse(BaseModel):
    profile_id: str
    offer_id: str
    status: str
    decided_at: str
