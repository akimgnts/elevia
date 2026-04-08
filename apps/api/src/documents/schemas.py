"""
schemas.py — Pydantic v2 strict models for CV Generator v1.

CvRequest       → POST /documents/cv input
CvDocumentPayload → content produced (cached or live)
CvDocumentResponse → API response envelope
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

PROMPT_VERSION = "cv_v1"
LETTER_TEMPLATE_VERSION = "letter_v0"


# ── Enums ─────────────────────────────────────────────────────────────────────

class AutonomyEnum(str, Enum):
    CONTRIB = "CONTRIB"
    COPILOT = "COPILOT"
    LEAD = "LEAD"


# ── Sub-models ────────────────────────────────────────────────────────────────

class ExperienceBlock(BaseModel):
    title: str = Field(..., max_length=120)
    company: str = Field(..., max_length=100)
    dates: Optional[str] = Field(default=None, max_length=80)
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


class CvExperienceView(BaseModel):
    role: str = Field(..., max_length=120)
    company: str = Field(default="", max_length=120)
    dates: Optional[str] = Field(default=None, max_length=80)
    bullets: List[str] = Field(default_factory=list, max_length=5)
    decision: Literal["keep", "compress", "drop"] = "keep"


class CvStructuredView(BaseModel):
    title: str = Field(..., max_length=160)
    experiences: List[CvExperienceView] = Field(default_factory=list, max_length=5)
    skills: List[str] = Field(default_factory=list, max_length=14)
    education: List[str] = Field(default_factory=list, max_length=6)
    layout: Literal["single_column"] = "single_column"


class ExperienceScoreDebug(BaseModel):
    role: str
    company: str = ""
    score: float
    skill_match: float
    job_similarity: float
    quantified_evidence: float
    sector_similarity: float
    recency: float
    autonomy: float
    decision: Literal["keep", "compress", "drop"]
    reasons: List[str] = Field(default_factory=list)


class SelectedVerbDebug(BaseModel):
    experience_role: str
    source_fragment: str
    domain: str
    family: str
    verb: str


class CvDebugPayload(BaseModel):
    parsed_offer: Dict[str, Any] = Field(default_factory=dict)
    experience_scores: List[ExperienceScoreDebug] = Field(default_factory=list)
    selected_verbs: List[SelectedVerbDebug] = Field(default_factory=list)
    missing_data: List[str] = Field(default_factory=list)


# ── Top-level payload (cached & returned) ─────────────────────────────────────

class CvDocumentPayload(BaseModel):
    summary: str = Field(..., max_length=600)
    keywords_injected: List[str] = Field(default_factory=list, max_length=12)
    experience_blocks: List[ExperienceBlock] = Field(default_factory=list, max_length=5)
    ats_notes: AtsNotes
    cv: Optional[CvStructuredView] = None
    debug: Optional[CvDebugPayload] = None
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


# ── For-offer endpoint (inbox-contextualised) ─────────────────────────────────

class InboxContext(BaseModel):
    """
    Optional context forwarded from the inbox match result.
    Used to enrich CV ordering (matched skills first) without recomputing.
    """
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    offer_cluster: Optional[str] = None
    profile_cluster: Optional[str] = None


class ForOfferRequest(BaseModel):
    """POST /documents/cv/for-offer input."""
    offer_id: str = Field(..., min_length=1)
    profile: Optional[dict] = None
    profile_id: Optional[str] = None
    lang: Literal["fr", "en"] = "fr"
    context: Optional[InboxContext] = None  # Inbox match context for enrichment


class ForOfferResponse(BaseModel):
    """POST /documents/cv/for-offer response."""
    ok: bool = True
    document: CvDocumentPayload           # Enriched payload (matched skills first)
    preview_text: str = ""                # Markdown render, ready to download
    context_used: bool = False            # True when inbox context drove ordering
    duration_ms: int = 0


# ── HTML CV (rendered) ───────────────────────────────────────────────────────

class CvHtmlMeta(BaseModel):
    offer_id: str
    prompt_version: str
    cache_hit: bool = False
    fallback_used: bool = False
    template_version: str = "cv_v1"


class CvHtmlResponse(BaseModel):
    ok: bool = True
    html: str
    meta: CvHtmlMeta
    duration_ms: int = 0


# ── Cover letter (deterministic, no LLM) ─────────────────────────────────────

class CoverLetterBlock(BaseModel):
    label: Literal["hook", "match", "value", "closing"]
    text: str = Field(..., max_length=600)


class CoverLetterMeta(BaseModel):
    offer_id: str
    template_version: str = LETTER_TEMPLATE_VERSION
    context_used: bool = False


class CoverLetterPayload(BaseModel):
    blocks: List[CoverLetterBlock] = Field(..., min_length=1, max_length=4)
    meta: CoverLetterMeta


class ForOfferLetterRequest(BaseModel):
    offer_id: str = Field(..., min_length=1)
    profile: Optional[dict] = None
    profile_id: Optional[str] = None
    lang: Literal["fr", "en"] = "fr"
    context: Optional[InboxContext] = None


class ForOfferLetterResponse(BaseModel):
    ok: bool = True
    document: CoverLetterPayload
    preview_text: str = ""
    duration_ms: int = 0
