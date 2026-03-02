"""
compass/contracts.py — Stable data contracts for the Compass signal layer.

Field names are frozen for API stability.
No dependency on scoring core.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class OfferDescriptionStructuredV1(BaseModel):
    """
    Structured offer description produced by compass text_structurer v1.

    Deterministic. No ML/LLM. Same input → same output.
    """
    missions: List[str]           # up to 8 bullet points
    requirements: List[str]       # up to 6 profile requirements
    tools_stack: List[str]        # up to 12 detected tools/technologies
    context: List[str]            # context tags (remote, hybride, vie, etc.)
    red_flags: List[str]          # heuristic red flag keys
    extracted_sections: Optional[Dict[str, str]] = None  # debug only (ELEVIA_DEBUG_STRUCTURER=1)


class SkillRef(BaseModel):
    """Reference to a skill (ESCO URI + display label)."""
    uri: Optional[str] = None
    label: str


class ToolNote(BaseModel):
    """Detected tool with disambiguation result."""
    tool_key: str
    status: Literal["UNSPECIFIED", "SPECIFIED", "UNKNOWN"]
    sense: Optional[str] = None       # e.g. "finance" | "supply" | "data"
    hits: List[str] = []              # matched disambiguator tokens (capped)


class ExplainPayloadV1(BaseModel):
    """
    Full explain payload for offer detail view.

    score_core is read-only (from scoring result) — NOT recomputed here.
    All other fields are post-layer signals.
    """
    score_core: float
    confidence: Literal["LOW", "MED", "HIGH"]
    incoherence_reasons: List[str]     # sorted, stable
    matched_skills: List[SkillRef]     # by (-idf, label), capped at max_list_items_ui
    missing_offer_skills: List[SkillRef]
    coverage_ratio: float              # |matched ∩ offer| / |offer|
    rare_signal: float                 # IDF-weighted match ratio
    rare_signal_level: Literal["LOW", "MED", "HIGH"]
    generic_ratio: float               # fraction of matched weight that is generic
    cluster_level: Literal["STRICT", "NEIGHBOR", "OUT"]
    tool_notes: List[ToolNote]
    # Sector signal (optional — requires cluster_idf_table at call site)
    sector_signal: Optional[float] = None
    sector_signal_level: Optional[Literal["LOW", "MED", "HIGH"]] = None
    sector_signal_note: Optional[str] = None
    debug_trace: Optional[Dict[str, Any]] = None  # only when ELEVIA_DEBUG_SIGNAL=1


class ExplainPayloadV1Compact(BaseModel):
    """
    Compact version of ExplainPayloadV1 for inbox list view.
    Omits large lists; keeps decision-relevant signals only.
    """
    score_core: float
    confidence: Literal["LOW", "MED", "HIGH"]
    cluster_level: Literal["STRICT", "NEIGHBOR", "OUT"]
    rare_signal_level: Literal["LOW", "MED", "HIGH"]
    incoherence_reasons: List[str]      # top 2
    matched_count: int
    missing_count: int
    # Sector signal (optional — matches ExplainPayloadV1)
    sector_signal: Optional[float] = None
    sector_signal_level: Optional[Literal["LOW", "MED", "HIGH"]] = None
    sector_signal_note: Optional[str] = None


# ── COMPASS D+ — Profile Structurer v1 contracts ──────────────────────────────

class ExperienceV1(BaseModel):
    """
    One professional experience block extracted from CV.

    autonomy_level heuristic (rule-based, no ML):
      HIGH  — lead / pilotage / responsable / owner / directeur
      MED   — contribution / équipe / collaborat* / chef de projet
      LOW   — support / assistant / stagiaire / apprenti

    impact_signals: regex-matched evidence of quantified impact.
    """
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None    # "MM/YYYY" or "YYYY" or None
    end_date: Optional[str] = None      # "MM/YYYY" | "YYYY" | "présent" | None
    duration_months: Optional[int] = None
    bullets: List[str] = []
    tools: List[str] = []
    skills: List[str] = []
    autonomy_level: Literal["LOW", "MED", "HIGH"] = "MED"
    impact_signals: List[str] = []      # matched evidence strings, capped at 5


class EducationV1(BaseModel):
    """
    One education block extracted from CV.

    cluster_hint: rule-based mapping of field → cluster key.
    """
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    cluster_hint: Optional[str] = None  # DATA_IT | FINANCE | SUPPLY_OPS | MARKETING_SALES | None


class CertificationV1(BaseModel):
    """One certification found in CV, with optional registry match."""
    name: str
    bundle_skills: List[str] = []       # from certifications_registry.json
    cluster_hint: Optional[str] = None  # from registry, or None if unmapped
    mapped: bool = False                # True if found in registry


class CVQualityCoverage(BaseModel):
    """Coverage sub-object for CVQualityV1."""
    experiences_found: int
    education_found: int
    certifications_found: int
    tools_found: int
    date_coverage_ratio: float          # fraction of experiences with ≥1 date


class CVQualityV1(BaseModel):
    """
    Heuristic CV quality assessment.

    quality_level:
      LOW  — no experience, no dates, wall of text (>800 chars no structure),
             tools_found < 2, or experiences_found == 0
      MED  — partial structure, incomplete dates
      HIGH — sections detected, ≥1 experience with dates, ≥3 tools, ≥1 impact signal

    NOT a judgment of the candidate — only of CV exploitability for matching.
    Does NOT influence score_core.
    """
    quality_level: Literal["LOW", "MED", "HIGH"]
    reasons: List[str]
    coverage: CVQualityCoverage


class ProfileStructuredV1(BaseModel):
    """
    Full structured view of a candidate CV.

    Deterministic. No ML/LLM. Same input → same output.
    score_core is NEVER touched by this layer.
    """
    experiences: List[ExperienceV1] = []
    education: List[EducationV1] = []
    certifications: List[CertificationV1] = []
    extracted_tools: List[str] = []         # aggregated across all experiences, capped at 50
    extracted_companies: List[str] = []
    extracted_titles: List[str] = []
    inferred_cluster_hints: List[str] = []  # deduplicated hints from education + certs
    cv_quality: CVQualityV1
    extracted_sections: Optional[Dict[str, str]] = None  # debug only (ELEVIA_DEBUG_PROFILE_STRUCT=1)


# ── COMPASS E — Cluster-Aware Enrichment + Market Radar contracts ─────────────

class ClusterDomainSkill(BaseModel):
    """
    One non-ESCO skill token tracked in the cluster library.

    status lifecycle: PENDING → ACTIVE (via activation rules) | REJECTED (validation fail)
    source: CV | OFFER | BOTH | LLM
    score_core is NEVER touched by this layer.
    """
    id: str                                    # md5(cluster|token_normalized)[:16]
    cluster: str
    token_normalized: str
    occurrences_cv: int = 0
    occurrences_offers: int = 0
    first_seen_at: str                         # ISO-8601 UTC
    last_seen_at: str
    status: Literal["PENDING", "ACTIVE", "REJECTED"] = "PENDING"
    source: Literal["CV", "OFFER", "BOTH", "LLM"] = "CV"
    validation_score: float = 0.0


class CVEnrichmentResult(BaseModel):
    """
    Result of CV enrichment pass through the cluster library.

    domain_skills_active: ACTIVE library tokens for this cluster (display/context only)
    domain_skills_pending: newly recorded PENDING tokens from this CV
    llm_triggered: True if LLM was called (ESCO count < threshold)
    llm_suggestions: validated tokens suggested by LLM
    score_core is NEVER present here.
    """
    cluster: Optional[str] = None
    domain_skills_active: List[str] = []
    domain_skills_pending: List[str] = []
    new_tokens_added: List[str] = []
    llm_triggered: bool = False
    llm_suggestions: List[Dict[str, str]] = []


class MarketRadarReport(BaseModel):
    """Market radar: emerging non-ESCO skills detected from offer ingestion."""
    generated_at: str
    top_emerging_per_cluster: Dict[str, List[str]] = {}
    new_active_skills: List[str] = []
    pending_skills: List[str] = []
    rejected_tokens: List[str] = []


class ClusterLibraryMetrics(BaseModel):
    """Operational metrics for the cluster domain skill library."""
    generated_at: str
    total_clusters: int
    active_per_cluster: Dict[str, int] = {}
    pending_per_cluster: Dict[str, int] = {}
    llm_calls_total: int = 0
    llm_calls_avoided: int = 0
    new_skills_via_offers: int = 0
    drift_index_per_cluster: Dict[str, float] = {}   # pending / (active + 1)
