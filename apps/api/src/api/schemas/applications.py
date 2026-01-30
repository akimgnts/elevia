"""
applications.py - Pydantic schemas for Applications Tracker endpoints.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    shortlisted = "shortlisted"
    applied = "applied"
    dismissed = "dismissed"


class ApplicationItem(BaseModel):
    id: str
    offer_id: str
    status: ApplicationStatus
    note: Optional[str] = None
    next_follow_up_date: Optional[str] = None
    created_at: str
    updated_at: str


class ApplicationCreate(BaseModel):
    offer_id: str
    status: ApplicationStatus
    note: Optional[str] = None
    next_follow_up_date: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    note: Optional[str] = None
    next_follow_up_date: Optional[str] = None


class ApplicationListResponse(BaseModel):
    items: List[ApplicationItem] = Field(default_factory=list)
