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


class NearMatchItem(BaseModel):
    profile_skill_id: str
    profile_label: str
    offer_skill_id: str
    offer_label: str
    relation: str
    strength: float


class NearMatchSummary(BaseModel):
    count: int = 0
    max_strength: float = 0.0
    avg_strength: float = 0.0


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
    matched_core: List[SkillExplainItem] = Field(default_factory=list)
    missing_core: List[SkillExplainItem] = Field(default_factory=list)
    matched_secondary: List[SkillExplainItem] = Field(default_factory=list)
    missing_secondary: List[SkillExplainItem] = Field(default_factory=list)
    matched_context: List[SkillExplainItem] = Field(default_factory=list)
    missing_context: List[SkillExplainItem] = Field(default_factory=list)
    breakdown: ExplainBreakdown
    near_matches: List[NearMatchItem] = Field(default_factory=list)
    near_match_count: int = 0
    near_match_summary: Optional[NearMatchSummary] = None


class OfferExplanation(BaseModel):
    """Clean front-ready explanation payload. Purely derived from matching output."""
    score: Optional[int] = Field(default=None, ge=0, le=100)
    fit_label: str
    summary_reason: str
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)


class OfferRoleHypothesis(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class OfferIntelligence(BaseModel):
    dominant_role_block: str
    secondary_role_blocks: List[str] = Field(default_factory=list)
    dominant_domains: List[str] = Field(default_factory=list)
    top_offer_signals: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    optional_skills: List[str] = Field(default_factory=list)
    role_hypotheses: List[OfferRoleHypothesis] = Field(default_factory=list)
    offer_summary: str
    role_block_scores: List[Dict[str, Any]] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None


class SemanticRoleAlignment(BaseModel):
    profile_role: str
    offer_role: str
    alignment: str = Field(..., pattern="^(high|medium|low)$")


class SemanticDomainAlignment(BaseModel):
    shared_domains: List[str] = Field(default_factory=list)
    profile_only_domains: List[str] = Field(default_factory=list)
    offer_only_domains: List[str] = Field(default_factory=list)


class SemanticSignalAlignment(BaseModel):
    matched_signals: List[str] = Field(default_factory=list)
    missing_core_signals: List[str] = Field(default_factory=list)


class SemanticExplainability(BaseModel):
    role_alignment: SemanticRoleAlignment
    domain_alignment: SemanticDomainAlignment
    signal_alignment: SemanticSignalAlignment
    alignment_summary: str


# ── Compass signal compact (display-only, always computed) ────────────────────

class CompassExplainCompact(BaseModel):
    """
    Compact Compass signal payload for inbox list view.
    Display-only — does NOT affect scoring or ranking.
    """
    score_core: float
    confidence: str  # LOW | MED | HIGH
    cluster_level: str  # STRICT | NEIGHBOR | OUT
    rare_signal_level: str  # LOW | MED | HIGH
    incoherence_reasons: List[str] = Field(default_factory=list)  # top 2
    matched_count: int = 0
    missing_count: int = 0
    # Sector signal (optional — populated when sector_signal_enabled=true)
    sector_signal: Optional[float] = None
    sector_signal_level: Optional[str] = None  # LOW | MED | HIGH
    sector_signal_note: Optional[str] = None


# ── Main item/response ────────────────────────────────────────────────────────

class InboxItem(BaseModel):
    offer_id: str
    source: Optional[str] = None
    title: str
    company: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    publication_date: Optional[str] = None
    is_vie: Optional[bool] = None
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
    explanation: Optional[OfferExplanation] = None  # always populated when matching ran
    offer_intelligence: Optional[OfferIntelligence] = None
    semantic_explainability: Optional[SemanticExplainability] = None
    explain_v1: Optional[CompassExplainCompact] = None  # compass signal (always computed)
    near_match_count: Optional[int] = None  # compact, display-only (list view)
    match_strength: Optional[str] = Field(default=None, pattern="^(STRONG|MEDIUM|WEAK)$")
    core_matched_count: Optional[int] = None
    core_total_count: Optional[int] = None
    dominant_reason: Optional[str] = None
    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    why_match: List[str] = Field(default_factory=list)
    main_blockers: List[str] = Field(default_factory=list)
    distance: Optional[str] = None
    next_move: Optional[str] = None


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
    total_estimate: Optional[int] = None
    applied_filters: Optional[Dict[str, Any]] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
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
