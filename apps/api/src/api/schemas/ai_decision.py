"""
AI Decision Layer schemas.
All types used by POST /ai/justify and the justification_layer module.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models for JustificationPayload
# ---------------------------------------------------------------------------

class TrueGap(BaseModel):
    skill: str
    severity: Literal["blocking", "semi_blocking", "minor"]
    why: str
    mitigation: Optional[str] = None


class NonSkillRequirement(BaseModel):
    text: str
    type: Literal[
        "tool",
        "context",
        "hr_jargon",
        "seniority_marker",
        "soft_skill",
        "domain_knowledge",
    ]
    why_not_gap: str


class TransferableStrength(BaseModel):
    strength: str
    evidence: str
    relevance: str


class CvStrategy(BaseModel):
    angle: str
    focus: str
    positioning_phrase: str


class JustificationMeta(BaseModel):
    offer_id: str
    profile_id: Optional[str] = None
    duration_ms: int
    llm_used: bool
    fallback_used: bool
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Core justification payload (returned inside JustifyFitResponse)
# ---------------------------------------------------------------------------

class JustificationPayload(BaseModel):
    decision: Literal["GO", "MAYBE", "NO_GO"]
    fit_summary: str
    true_gaps: List[TrueGap] = Field(default_factory=list)
    non_skill_requirements: List[NonSkillRequirement] = Field(default_factory=list)
    transferable_strengths: List[TransferableStrength] = Field(default_factory=list)
    cv_strategy: CvStrategy
    application_effort: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: float = Field(ge=0.0, le=1.0)
    archetype: Optional[str] = None
    meta: JustificationMeta


# ---------------------------------------------------------------------------
# Request / Response for POST /ai/justify
# ---------------------------------------------------------------------------

class JustifyFitRequest(BaseModel):
    offer_id: str
    profile: Dict[str, Any]
    profile_id: Optional[str] = None
    score: Optional[int] = None                         # 0–100
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    canonical_skills: List[str] = Field(default_factory=list)
    enriched_signals: List[str] = Field(default_factory=list)
    concept_signals: List[str] = Field(default_factory=list)
    profile_intelligence: Optional[Dict[str, Any]] = None
    offer_intelligence: Optional[Dict[str, Any]] = None
    include_cv: bool = False


class JustifyFitResponse(BaseModel):
    ok: bool
    justification: JustificationPayload
    cv_document: Optional[Dict[str, Any]] = None        # present only when include_cv=True
    duration_ms: int


# ---------------------------------------------------------------------------
# Legacy stub models (kept for import safety — not connected to any route)
# ---------------------------------------------------------------------------

class ApplicationFitScore(BaseModel):
    """Contextual fit interpretation for one application."""
    application_id: str
    offer_id: str
    score: float
    reasoning: str
    suggested_status: Optional[str] = None


class NextStatusSuggestion(BaseModel):
    """AI-suggested next pipeline stage for an application."""
    application_id: str
    current_status: str
    suggested_status: str
    confidence: float
    rationale: str


class RankedApplication(BaseModel):
    application_id: str
    offer_id: str
    rank: int
    opportunity_score: float
    reason: str


class ApplicationRanking(BaseModel):
    """Ranked list of applications by opportunity score."""
    user_id: str
    items: List[RankedApplication]
