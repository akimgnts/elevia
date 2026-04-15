"""
applications.py - Pydantic schemas for Applications Tracker endpoints.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    saved = "saved"
    cv_ready = "cv_ready"
    applied = "applied"
    follow_up = "follow_up"
    interview = "interview"
    rejected = "rejected"
    won = "won"
    archived = "archived"


class ApplicationItem(BaseModel):
    id: str
    user_id: Optional[str] = None
    offer_id: str
    offer_title: Optional[str] = None
    offer_company: Optional[str] = None
    offer_city: Optional[str] = None
    offer_country: Optional[str] = None
    status: ApplicationStatus
    source: str = "manual"
    note: Optional[str] = None
    next_follow_up_date: Optional[str] = None
    current_cv_cache_key: Optional[str] = None
    current_letter_cache_key: Optional[str] = None
    created_at: str
    updated_at: str
    applied_at: Optional[str] = None
    last_status_change_at: Optional[str] = None
    # Preparatory field for AI strategy layer (v0 — not yet LLM-generated)
    strategy_hint: Optional[str] = None


class ApplicationCreate(BaseModel):
    offer_id: str
    status: ApplicationStatus
    source: str = "manual"
    note: Optional[str] = None
    next_follow_up_date: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    note: Optional[str] = None
    next_follow_up_date: Optional[str] = None
    strategy_hint: Optional[str] = None


class ApplicationListResponse(BaseModel):
    items: List[ApplicationItem] = Field(default_factory=list)


class ApplicationHistoryItem(BaseModel):
    id: str
    application_id: str
    from_status: Optional[str] = None
    to_status: str
    changed_at: str
    note: Optional[str] = None


class ApplicationHistoryResponse(BaseModel):
    items: List[ApplicationHistoryItem] = Field(default_factory=list)


class PrepareRequest(BaseModel):
    profile: Optional[Dict[str, Any]] = None
    enrich_llm: int = Field(default=0, ge=0, le=1)


class PrepareResponse(BaseModel):
    ok: bool
    application_id: str
    offer_id: str
    run_id: str
    cv_cache_key: Optional[str] = None
    letter_cache_key: Optional[str] = None
    status: str
    warnings: List[str] = Field(default_factory=list)
