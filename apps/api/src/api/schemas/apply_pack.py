"""
apply_pack.py — Pydantic schemas for POST /apply-pack.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApplyPackOfferIn(BaseModel):
    """Minimal offer data needed for apply-pack generation."""
    id: str
    title: str
    company: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class ApplyPackProfileIn(BaseModel):
    """Minimal profile data needed for apply-pack generation."""
    id: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    name: Optional[str] = None


class ApplyPackRequest(BaseModel):
    """Request body for POST /apply-pack."""
    profile: ApplyPackProfileIn
    offer: ApplyPackOfferIn
    matched_core: Optional[List[str]] = None   # pre-computed; if absent, computed server-side
    missing_core: Optional[List[str]] = None   # pre-computed; if absent, computed server-side
    enrich_llm: int = Field(default=0, ge=0, le=1, description="1 = attempt LLM rewrite")


class ApplyPackMeta(BaseModel):
    """Summary metadata returned with every apply-pack response."""
    offer_id: str
    offer_title: str
    company: str
    matched_core: List[str]
    missing_core: List[str]
    generated_at: str    # ISO 8601


class ApplyPackResponse(BaseModel):
    """Response from POST /apply-pack."""
    mode: str              # "baseline" | "baseline+llm"
    cv_text: str
    letter_text: str
    meta: ApplyPackMeta
    warnings: List[str] = Field(default_factory=list)
