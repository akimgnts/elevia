"""
schemas.py — Pydantic v2 strict models for CV Generator v1.

CvRequest       → POST /documents/cv input
CvDocumentPayload → content produced (cached or live)
CvDocumentResponse → API response envelope
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

PROMPT_VERSION = "cv_v1"


# ── Enums ─────────────────────────────────────────────────────────────────────

class AutonomyEnum(str, Enum):
    CONTRIB = "CONTRIB"
    COPILOT = "COPILOT"
    LEAD = "LEAD"


# ── Sub-models ────────────────────────────────────────────────────────────────

class ExperienceBlock(BaseModel):
    title: str = Field(..., max_length=120)
    company: str = Field(..., max_length=100)
    bullets: List[str] = Field(..., min_length=1, max_length=5)
    tools: List[str] = Field(default_factory=list, max_length=8)
    autonomy: AutonomyEnum = AutonomyEnum.COPILOT
    impact: Optional[str] = Field(default=None, max_length=240)


class AtsNotes(BaseModel):
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    ats_score_estimate: int = Field(default=0, ge=0, le=100)


class CvMeta(BaseModel):
    offer_id: str
    profile_fingerprint: str
    prompt_version: str = PROMPT_VERSION
    cache_hit: bool = False
    fallback_used: bool = False


# ── Top-level payload (cached & returned) ─────────────────────────────────────

class CvDocumentPayload(BaseModel):
    summary: str = Field(..., max_length=600)
    keywords_injected: List[str] = Field(default_factory=list, max_length=12)
    experience_blocks: List[ExperienceBlock] = Field(default_factory=list, max_length=3)
    ats_notes: AtsNotes
    meta: CvMeta


# ── API I/O ───────────────────────────────────────────────────────────────────

class CvRequest(BaseModel):
    profile: Optional[dict] = None
    profile_id: Optional[str] = None
    offer_id: str = Field(..., min_length=1)
    lang: Literal["fr", "en"] = "fr"
    style: Literal["ats_compact"] = "ats_compact"


class CvDocumentResponse(BaseModel):
    ok: bool = True
    document: CvDocumentPayload
    duration_ms: int = 0
