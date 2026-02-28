"""
inbox.py - Pydantic schemas for Inbox endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InboxRequest(BaseModel):
    profile_id: str
    profile: Dict[str, Any]
    min_score: int = Field(default=10, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)
    explain: bool = False  # When True, include ExplainBlock per item (no scoring change)


class RomeLink(BaseModel):
    rome_code: str
    rome_label: str


class RomeCompetence(BaseModel):
    competence_code: str
    competence_label: str
    esco_uri: Optional[str] = None


class RomeInferred(BaseModel):
    """ROME code inferred from title (for offers without native ROME)."""
    rome_code: str
    rome_label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str
    version: str


# ── Explain block (display-only, no scoring change) ───────────────────────────

class SkillExplainItem(BaseModel):
    """A skill with optional 'weighted' flag for display."""
    label: str
    weighted: bool = False  # True if skill appears in ROME competences for this offer


class ExplainBreakdown(BaseModel):
    """Score component breakdown — consumed from match_debug, read-only."""
    skills_score: float   # contribution in 0–70 range
    skills_weight: int    # 70
    language_score: float # contribution in 0–15 range
    language_weight: int  # 15
    language_match: bool
    education_score: float  # contribution in 0–10 range
    education_weight: int   # 10
    education_match: bool
    country_score: float  # contribution in 0–5 range
    country_weight: int   # 5
    country_match: bool
    total: float          # 0–100 (pre-rounding)


class ExplainBlock(BaseModel):
    """
    Display-only justification per offer.
    Populated only when InboxRequest.explain=True.
    Does NOT affect scoring or ranking.
    """
    matched_display: List[SkillExplainItem]  # top 6 for card
    missing_display: List[SkillExplainItem]  # top 6 for card
    matched_full: List[SkillExplainItem]     # all matched, max 30
    missing_full: List[SkillExplainItem]     # all missing, max 30
    breakdown: ExplainBreakdown


# ── Main item/response ────────────────────────────────────────────────────────

class InboxItem(BaseModel):
    offer_id: str
    title: str
    company: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    score: int = Field(..., ge=0, le=100)
    score_pct: Optional[int] = Field(default=None, ge=0, le=100)
    score_raw: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    display_description: Optional[str] = None
    description_snippet: Optional[str] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    matched_skills_display: List[str] = Field(default_factory=list)
    missing_skills_display: List[str] = Field(default_factory=list)
    unmapped_tokens: List[str] = Field(default_factory=list)
    offer_uri_count: Optional[int] = None
    profile_uri_count: Optional[int] = None
    intersection_count: Optional[int] = None
    scoring_unit: Optional[str] = None
    skills_uri_count: Optional[int] = None
    skills_uri_collapsed_dupes: Optional[int] = None
    skills_unmapped_count: Optional[int] = None
    offer_cluster: Optional[str] = None
    domain_bucket: Optional[str] = Field(default=None, pattern="^(strict|neighbor|out)$")
    signal_score: Optional[float] = None
    coherence: Optional[str] = Field(default=None, pattern="^(ok|suspicious)$")
    rome: Optional[RomeLink] = None
    rome_competences: List[RomeCompetence] = Field(default_factory=list)
    rome_inferred: Optional[RomeInferred] = None
    explain: Optional[ExplainBlock] = None  # populated when request.explain=True


class InboxMeta(BaseModel):
    profile_cluster: Optional[str] = None
    gating_mode: Optional[str] = Field(
        default=None,
        pattern="^(IN_DOMAIN|STRICT_PLUS_NEIGHBORS|OUT_OF_DOMAIN)$",
    )
    coverage_before: Optional[int] = None
    coverage_after: Optional[int] = None
    suggest_out_of_domain: Optional[bool] = None
    out_of_domain_count: Optional[int] = None
    cluster_distribution_top20: Optional[Dict[str, int]] = None
    strict_count: Optional[int] = None
    neighbor_count: Optional[int] = None
    out_count: Optional[int] = None


class InboxResponse(BaseModel):
    profile_id: str
    items: List[InboxItem]
    total_matched: int
    total_decided: int
    meta: Optional[InboxMeta] = None


class DecisionRequest(BaseModel):
    profile_id: str
    status: str = Field(..., pattern="^(SHORTLISTED|DISMISSED)$")
    note: Optional[str] = None


class DecisionResponse(BaseModel):
    profile_id: str
    offer_id: str
    status: str
    decided_at: str


class OfferSemanticRequest(BaseModel):
    profile_id: str


class OfferSemanticResponse(BaseModel):
    offer_id: str
    semantic_score: Optional[float] = None
    semantic_model_version: Optional[str] = None
    relevant_passages: List[str] = Field(default_factory=list)
    ai_available: bool = False
    ai_error: Optional[str] = None
