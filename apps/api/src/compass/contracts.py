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
