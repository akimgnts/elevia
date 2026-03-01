"""
compass/contracts.py — Stable data contracts for the Compass signal layer.

Field names are frozen for API stability.
No dependency on scoring core.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


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
